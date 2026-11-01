# deskcap build: clean-room PipeWire virtual camera node.
# Deps: libpipewire-0.3 dev headers only. No turbojpeg, no libswscale.
CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra
PW_CFLAGS := $(shell pkg-config --cflags libpipewire-0.3)
PW_LIBS := $(shell pkg-config --libs libpipewire-0.3)

all: deskcap

deskcap: pwcam_desktop.c
	$(CC) $(CFLAGS) $(PW_CFLAGS) -o $@ $< $(PW_LIBS) -pthread

clean:
	rm -f deskcap

.PHONY: all clean
