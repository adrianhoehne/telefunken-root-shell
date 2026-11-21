/* Payload v7: wie v6, plus Netflix beim Boot abschalten.
 *
 * Netflix ist in der App-Liste `netflix=y` (read-only /vendor) und startet
 * resident mit Verzögerung. Der Payload killt es einmal, sobald es auftaucht
 * (20–60 s nach Boot). Manueller Start über die Netflix-Taste bleibt möglich.
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
        "(sleep 20; for i in 1 2 3 4 5 6 7 8; do p=$(pidof netflix); "
        " [ -n \"$p\" ] && { kill $p 2>/dev/null; break; }; sleep 5; done &); "
        "echo \"[boot] payload v7\" >> /tmp/tv.log 2>/dev/null; "
        "if [ -f /conf/remotelf/logd ]; then "
        "  cp -f /conf/remotelf/logd /tmp/ && (/tmp/logd >/dev/null 2>&1 &); "
        "fi; "
        "if [ -f /conf/remotelf/libkeyhook.so ]; then "
        "  cp -f /conf/remotelf/libkeyhook.so /tmp/ && "
        "  exec env LD_PRELOAD=/tmp/libkeyhook.so /vendor/com.nvt.idtv/aurora.elf >> /tmp/app.log 2>&1; "
        "fi; "
        "exec /vendor/com.nvt.idtv/aurora.elf >> /tmp/app.log 2>&1";
    execl("/bin/sh", "sh", "-c", cmd, (char *)0);
    return 0;
}
