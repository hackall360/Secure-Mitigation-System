/* Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
 * https://polyformproject.org/licenses/noncommercial/1.0.0
 * Deliberately vulnerable local fixture. Run only through DockerSandboxManager.
 * binary_argv_echo: echoes argv[1] unsanitized into stdout. The boundary is
 * an unbounded, unvalidated argv/stdin reflection: overlong or metachar-heavy
 * input reaches output verbatim instead of being rejected or truncated.
 * The trusted contract (enforced by harness checks, not by this binary):
 * argv[1] longer than 64 bytes or containing ';', '&', '|', '$', '`' must be
 * rejected by the mitigated harness; short alnum input echoes back.
 */
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc < 2) {
        printf("usage: echo argv[1]\n");
        return 0;
    }
    /* VULNERABLE: no length cap, no metacharacter policy. */
    printf("echo: %s\n", argv[1]);
    return 0;
}
