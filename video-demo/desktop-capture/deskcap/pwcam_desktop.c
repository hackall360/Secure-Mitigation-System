/*
 * deskcap — headless desktop-capture virtual camera (clean-room implementation).
 *
 * Publishes a PipeWire Video/Source node ("Desktop Capture Camera") that
 * behaves like a fixed-capability hardware webcam so WebRTC consumers
 * (Firefox, Chrome, Discord, ...) can pull buffers without a desktop
 * portal prompt.
 *
 * Pipeline this node terminates:
 *   gamescope (nested 1920x1080 Wayland session)
 *     -> wf-recorder (rawvideo yuv420p to stdout)
 *     -> deskcap stdin (this binary)
 *     -> PipeWire Video/Source node
 *
 * Contract (locked, no negotiation range):
 *   - EnumFormat: exactly one capability, I420 1920x1080 @ 60/1.
 *   - SPA_PARAM_Buffers offers MemFd | MemPtr (the non-DmaBuf path
 *     WebRTC capturers map) plus a Header meta.
 *   - Frames arrive on stdin as raw uncompressed I420 planes, exactly
 *     3110400 bytes each (1920 * 1080 * 3 / 2). No JPEG decoding, no
 *     scaling, no conversion: reader_thread fills a slot, on_process
 *     memcpy's it straight into the server-allocated SPA buffer.
 *   - stdin EOF quits the main loop so the launcher can respawn.
 *
 * Build: make (or make -C video-demo/desktop-capture/deskcap)
 */

#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <pipewire/pipewire.h>
#include <spa/buffer/meta.h>
#include <spa/debug/types.h>
#include <spa/param/video/format-utils.h>
#include <spa/param/video/type-info.h>
#include <spa/pod/builder.h>

#define DESKCAP_WIDTH 1920
#define DESKCAP_HEIGHT 1080
#define DESKCAP_FPS_NUM 60
#define DESKCAP_FPS_DEN 1
/* Exact byte size of one uncompressed 1080p I420 frame: W * H * 1.5. */
#define DESKCAP_FRAME_BYTES 3110400

_Static_assert(DESKCAP_FRAME_BYTES == DESKCAP_WIDTH * DESKCAP_HEIGHT * 3 / 2,
	       "frame size must equal W*H*1.5");

struct raw_slot {
	uint8_t *bytes;
};

struct deskcap {
	struct pw_main_loop *loop;
	struct pw_stream *stream;
	struct spa_source *ticker;
	struct spa_hook listener;

	/* Locked negotiated format. */
	struct spa_video_info_raw fmt;
	uint32_t stride;
	uint32_t nbytes;
	int fmt_ready;
	int flowing;

	/* Intake: reader thread publishes the newest full frame; the
	 * PipeWire loop thread swaps it in during on_process. */
	pthread_mutex_t guard;
	struct raw_slot fresh;
	int fresh_ready;
	uint8_t *live;          /* frame currently being served */

	uint64_t seq;
};

/* Paint I420 broadcast-black (Y=16, U=V=128) so consumers see black,
 * never garbage, before the first stdin frame lands. */
static void paint_black(uint8_t *dst)
{
	size_t y_size = (size_t)DESKCAP_WIDTH * DESKCAP_HEIGHT;
	memset(dst, 16, y_size);
	memset(dst + y_size, 128, y_size / 2);
}

/* Block until exactly n bytes are read; -1 on EOF or hard error. */
static int read_full(int fd, uint8_t *dst, size_t n)
{
	size_t got = 0;
	while (got < n) {
		ssize_t r = read(fd, dst + got, n - got);
		if (r == 0)
			return -1;
		if (r < 0) {
			if (errno == EINTR)
				continue;
			return -1;
		}
		got += (size_t)r;
	}
	return 0;
}

/* Runs off-loop: consume raw I420 frames from stdin forever. */
static void *reader_thread(void *arg)
{
	struct deskcap *dc = arg;
	uint8_t *staging = malloc(DESKCAP_FRAME_BYTES);
	if (!staging) {
		fprintf(stderr, "[deskcap] out of memory\n");
		pw_main_loop_quit(dc->loop);
		return NULL;
	}

	for (;;) {
		if (read_full(STDIN_FILENO, staging, DESKCAP_FRAME_BYTES) < 0)
			break;
		pthread_mutex_lock(&dc->guard);
		uint8_t *old = dc->fresh.bytes;
		dc->fresh.bytes = staging;
		staging = old ? old : malloc(DESKCAP_FRAME_BYTES);
		dc->fresh_ready = 1;
		pthread_mutex_unlock(&dc->guard);
		if (!staging) {
			fprintf(stderr, "[deskcap] out of memory\n");
			break;
		}
	}

	free(staging);
	fprintf(stderr, "[deskcap] stdin closed, exiting\n");
	pw_main_loop_quit(dc->loop);
	return NULL;
}

/* Called on the PipeWire loop thread: adopt the newest stdin frame. */
static void adopt_fresh(struct deskcap *dc)
{
	pthread_mutex_lock(&dc->guard);
	if (dc->fresh_ready && dc->fresh.bytes) {
		uint8_t *tmp = dc->live;
		dc->live = dc->fresh.bytes;
		dc->fresh.bytes = tmp;
		dc->fresh_ready = 0;
	}
	pthread_mutex_unlock(&dc->guard);
}

static void on_process(void *arg)
{
	struct deskcap *dc = arg;
	struct pw_buffer *b;
	struct spa_buffer *sbuf;
	struct spa_data *d;
	struct spa_meta_header *h;
	struct timespec now;

	if (!dc->fmt_ready)
		return;
	b = pw_stream_dequeue_buffer(dc->stream);
	if (!b)
		return;

	sbuf = b->buffer;
	d = &sbuf->datas[0];
	if (!d->data || d->maxsize < dc->nbytes) {
		pw_stream_queue_buffer(dc->stream, b);
		return;
	}

	adopt_fresh(dc);
	memcpy(d->data, dc->live, dc->nbytes);

	d->chunk->offset = 0;
	d->chunk->size = dc->nbytes;
	d->chunk->stride = (int32_t)dc->stride;
	d->chunk->flags = 0;

	h = spa_buffer_find_meta_data(sbuf, SPA_META_Header, sizeof(*h));
	if (h) {
		clock_gettime(CLOCK_MONOTONIC, &now);
		h->pts = SPA_TIMESPEC_TO_NSEC(&now);
		h->flags = 0;
		h->seq = dc->seq++;
		h->dts_offset = 0;
	}
	b->size = dc->nbytes;

	pw_stream_queue_buffer(dc->stream, b);
}

static void on_tick(void *arg, uint64_t expirations)
{
	struct deskcap *dc = arg;
	(void)expirations;
	pw_stream_trigger_process(dc->stream);
}

static void arm_ticker(struct deskcap *dc, int on)
{
	struct timespec kick = { 0, 1 };
	struct timespec every = { 0, 0 };
	uint64_t ns = (uint64_t)1000000000u * DESKCAP_FPS_DEN / DESKCAP_FPS_NUM;

	every.tv_sec = (time_t)(ns / 1000000000u);
	every.tv_nsec = (long)(ns % 1000000000u);
	pw_loop_update_timer(pw_main_loop_get_loop(dc->loop), dc->ticker,
			     on ? &kick : NULL, on ? &every : NULL, false);
}

static void on_state(void *arg, enum pw_stream_state old_state,
		     enum pw_stream_state state, const char *error)
{
	struct deskcap *dc = arg;
	(void)old_state;

	fprintf(stderr, "[deskcap] stream state: %s%s%s\n",
		pw_stream_state_as_string(state),
		error ? " error: " : "", error ? error : "");

	if (state == PW_STREAM_STATE_STREAMING) {
		dc->flowing = 1;
		arm_ticker(dc, 1);
	} else if (dc->flowing) {
		dc->flowing = 0;
		arm_ticker(dc, 0);
	}
}

static void on_param(void *arg, uint32_t id, const struct spa_pod *param)
{
	struct deskcap *dc = arg;
	uint8_t pod_mem[1024];
	struct spa_pod_builder b = SPA_POD_BUILDER_INIT(pod_mem, sizeof(pod_mem));
	const struct spa_pod *answers[3];
	uint32_t n = 0;

	if (!param || id != SPA_PARAM_Format) {
		if (id == SPA_PARAM_Format)
			dc->fmt_ready = 0;
		return;
	}
	if (spa_format_video_raw_parse(param, &dc->fmt) < 0)
		return;

	/* Locked contract: I420 1920x1080 only. Anything else is refused
	 * so a consumer can never drag us into a geometry the stdin
	 * producer does not emit. */
	if (dc->fmt.format != SPA_VIDEO_FORMAT_I420 ||
	    dc->fmt.size.width != DESKCAP_WIDTH ||
	    dc->fmt.size.height != DESKCAP_HEIGHT) {
		pw_stream_set_error(dc->stream, -EINVAL,
				    "deskcap serves I420 1920x1080 only");
		return;
	}

	dc->stride = DESKCAP_WIDTH;
	dc->nbytes = DESKCAP_FRAME_BYTES;

	uint8_t *frame = realloc(dc->live, dc->nbytes);
	if (!frame)
		abort();
	dc->live = frame;
	paint_black(dc->live);
	pthread_mutex_lock(&dc->guard);
	if (!dc->fresh.bytes) {
		dc->fresh.bytes = malloc(dc->nbytes);
		if (!dc->fresh.bytes)
			abort();
		paint_black(dc->fresh.bytes);
	}
	pthread_mutex_unlock(&dc->guard);
	dc->fmt_ready = 1;

	fprintf(stderr, "[deskcap] locked format: I420 %ux%u @ %u/%u (%u bytes)\n",
		dc->fmt.size.width, dc->fmt.size.height,
		dc->fmt.framerate.num, dc->fmt.framerate.denom, dc->nbytes);

	/* WebRTC consumers map the non-DmaBuf path: offer MemFd|MemPtr
	 * with a Header meta, no modifiers. */
	answers[n++] = spa_pod_builder_add_object(&b,
		SPA_TYPE_OBJECT_ParamBuffers, SPA_PARAM_Buffers,
		SPA_PARAM_BUFFERS_buffers, SPA_POD_CHOICE_RANGE_Int(8, 2, 32),
		SPA_PARAM_BUFFERS_blocks, SPA_POD_Int(1),
		SPA_PARAM_BUFFERS_size, SPA_POD_Int((int32_t)dc->nbytes),
		SPA_PARAM_BUFFERS_stride, SPA_POD_Int((int32_t)dc->stride),
		SPA_PARAM_BUFFERS_dataType, SPA_POD_CHOICE_FLAGS_Int(
			(1u << SPA_DATA_MemFd) | (1u << SPA_DATA_MemPtr)));

	answers[n++] = spa_pod_builder_add_object(&b,
		SPA_TYPE_OBJECT_ParamMeta, SPA_PARAM_Meta,
		SPA_PARAM_META_type, SPA_POD_Id(SPA_META_Header),
		SPA_PARAM_META_size, SPA_POD_Int(sizeof(struct spa_meta_header)));

	pw_stream_update_params(dc->stream, answers, n);
}

static const struct pw_stream_events stream_events = {
	PW_VERSION_STREAM_EVENTS,
	.state_changed = on_state,
	.param_changed = on_param,
	.process = on_process,
};

static void handle_quit(void *arg, int sig)
{
	struct deskcap *dc = arg;
	(void)sig;
	pw_main_loop_quit(dc->loop);
}

int main(int argc, char *argv[])
{
	struct deskcap dc = { 0 };
	const struct spa_pod *caps[4];
	uint8_t caps_mem[4096];
	struct spa_pod_builder b = SPA_POD_BUILDER_INIT(caps_mem, sizeof(caps_mem));
	uint32_t n = 0;
	pthread_t reader;

	pw_init(&argc, &argv);
	pthread_mutex_init(&dc.guard, NULL);

	dc.live = malloc(DESKCAP_FRAME_BYTES);
	if (!dc.live) {
		fprintf(stderr, "[deskcap] out of memory\n");
		return 1;
	}
	paint_black(dc.live);

	dc.loop = pw_main_loop_new(NULL);
	if (!dc.loop) {
		fprintf(stderr, "[deskcap] cannot create main loop\n");
		return 1;
	}
	pw_loop_add_signal(pw_main_loop_get_loop(dc.loop), SIGINT, handle_quit, &dc);
	pw_loop_add_signal(pw_main_loop_get_loop(dc.loop), SIGTERM, handle_quit, &dc);
	dc.ticker = pw_loop_add_timer(pw_main_loop_get_loop(dc.loop), on_tick, &dc);

	dc.stream = pw_stream_new_simple(
		pw_main_loop_get_loop(dc.loop),
		"deskcap-desktop",
		pw_properties_new(
			PW_KEY_MEDIA_CLASS, "Video/Source",
			PW_KEY_MEDIA_ROLE, "Camera",
			PW_KEY_NODE_NAME, "deskcap-desktop",
			PW_KEY_NODE_DESCRIPTION, "Desktop Capture Camera",
			PW_KEY_NODE_NICK, "Deskcap",
			NULL),
		&stream_events, &dc);
	if (!dc.stream) {
		fprintf(stderr, "[deskcap] cannot create stream\n");
		return 1;
	}

	/* Exactly one capability, like a fixed-mode hardware webcam:
	 * I420 1920x1080 @ 60fps. */
	{
		struct spa_video_info_raw info = SPA_VIDEO_INFO_RAW_INIT(
			.format = SPA_VIDEO_FORMAT_I420,
			.size = SPA_RECTANGLE(DESKCAP_WIDTH, DESKCAP_HEIGHT),
			.framerate = SPA_FRACTION(DESKCAP_FPS_NUM, DESKCAP_FPS_DEN));
		caps[n++] = spa_format_video_raw_build(&b, SPA_PARAM_EnumFormat, &info);
	}

	if (pw_stream_connect(dc.stream, PW_DIRECTION_OUTPUT, PW_ID_ANY,
			      PW_STREAM_FLAG_DRIVER | PW_STREAM_FLAG_MAP_BUFFERS,
			      caps, n) < 0) {
		fprintf(stderr, "[deskcap] pw_stream_connect failed\n");
		return 1;
	}

	if (pthread_create(&reader, NULL, reader_thread, &dc) != 0) {
		fprintf(stderr, "[deskcap] cannot start reader thread\n");
		return 1;
	}

	fprintf(stderr, "[deskcap] node published, waiting for 1920x1080 I420 frames on stdin\n");
	pw_main_loop_run(dc.loop);

	pthread_join(reader, NULL);
	pw_stream_destroy(dc.stream);
	pw_main_loop_destroy(dc.loop);
	free(dc.live);
	free(dc.fresh.bytes);
	pw_deinit();
	return 0;
}
