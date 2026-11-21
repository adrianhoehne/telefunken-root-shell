/* Payload v6: wie v5, plus Logging — aber robust.
 *
 * Kritischer Pfad (Shells + App) berührt NUR /tmp und /dev, niemals /buffer
 * oder die SMB-Freigabe. /buffer ist beim Payload-Start evtl. noch nicht
 * gemountet; SMB-Schreibvorgänge können blockieren. Deshalb:
 *   - Boot-Ereignis  -> /tmp/tv.log
 *   - App-Ausgabe    -> /tmp/app.log
 *   - logd (Hintergrund) liest diese und schreibt auf die Freigabe
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
        "echo \"[boot] payload v6\" >> /tmp/tv.log 2>/dev/null; "
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
