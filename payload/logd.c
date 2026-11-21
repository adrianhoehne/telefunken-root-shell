/*
 * logd — sammelt Logs des Fernsehers und schreibt sie auf die SMB-Freigabe.
 *
 * Drei+eine Quellen:
 *   /proc/kmsg      -> log/kernel.log  (Kernel-Ringpuffer)
 *   /tmp/app.log    -> log/app.log     (stdout/stderr der TV-App)
 *   /tmp/tv.log     -> log/tv.log      (Boot-Ereignisse)
 *   /tmp/keylog.bin -> log/keys.log    (Tasten, dekodiert)
 *
 * Schlägt ein SMB-Schreibvorgang fehl (Freigabe kurz weg), wird die Zeile
 * verworfen statt zu blockieren. Lokale Quellen bleiben erhalten, damit beim
 * nächsten Durchlauf nichts verloren geht.
 *
 * Build: arm-linux-gnueabihf-gcc -static -Os -o logd logd.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>

#define KMSG    "/proc/kmsg"
#define APPLOG  "/tmp/app.log"
#define TVLOG   "/tmp/tv.log"
#define KEYLOG  "/tmp/keylog.bin"
#define SMBLOG  "/conf/remotelf/log"

static const char *keys[256];

static void init_keys(void) {
    keys[0x41] = "1"; keys[0x42] = "2"; keys[0x43] = "3"; keys[0x44] = "4";
    keys[0x45] = "5"; keys[0x46] = "6"; keys[0x47] = "7"; keys[0x48] = "8";
    keys[0x49] = "9"; keys[0x40] = "0";
    keys[0x55] = "LEFT"; keys[0x56] = "RIGHT"; keys[0x54] = "UP"; keys[0x53] = "DOWN";
    keys[0x60] = "CH+"; keys[0x61] = "CH-";
    keys[0x50] = "VOL-"; keys[0x51] = "VOL+";
    keys[0x75] = "OK"; keys[0x70] = "MENU"; keys[0x78] = "SOURCE";
    keys[0x77] = "RED"; keys[0x76] = "GREEN"; keys[0x72] = "YELLOW"; keys[0x74] = "BLUE";
    keys[0x58] = "STOP"; keys[0x59] = "PLAY"; keys[0x71] = "PAUSE";
    keys[0x5b] = "REWIND"; keys[0x5c] = "FORWARD"; keys[0x4c] = "STANDBY";
    keys[0x5f] = "SUBTITLE"; keys[0x7c] = "TEXT";
    keys[0x4d] = "MUTE"; keys[0x52] = "INFO"; keys[0x66] = "TV/DTV";
    keys[0x4b] = "WIDE"; keys[0x6f] = "EPG"; keys[0x73] = "REC";
}

static void append_smb(const char *name, const void *data, size_t len) {
    char path[160];
    int fd;
    snprintf(path, sizeof path, "%s/%s", SMBLOG, name);
    fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0)
        return;
    (void)write(fd, data, len);
    close(fd);
}

/* lokale Datei ab Offset lesen und neu Angekommenes auf SMB kopieren */
static long tail_forward(const char *local, const char *smbname, long off) {
    char buf[4096];
    int fd = open(local, O_RDONLY);
    ssize_t n;
    if (fd < 0)
        return off;
    lseek(fd, off, SEEK_SET);
    n = read(fd, buf, sizeof buf);
    if (n > 0) {
        append_smb(smbname, buf, (size_t)n);
        off += n;
    }
    close(fd);
    return off;
}

/* Event = FF FF + 7 Bytes; Tastendruck = 50 00 00 <addr> <cmd> 00 <chk> */
static void scan_keys(const unsigned char *buf, ssize_t n) {
    ssize_t i;
    for (i = 0; i + 8 < n; i++) {
        if (buf[i] == 0xFF && buf[i + 1] == 0xFF) {
            const unsigned char *p = &buf[i + 2];
            if (p[0] == 0x50 && p[5] == 0x00) {
                char line[128], ts[32];
                const char *name = keys[p[4]];
                time_t t = time(NULL);
                struct tm *tm = localtime(&t);
                strftime(ts, sizeof ts, "%Y-%m-%d %H:%M:%S", tm);
                if (name)
                    snprintf(line, sizeof line, "%s [key] %s\n", ts, name);
                else
                    snprintf(line, sizeof line, "%s [key] 0x%02x\n", ts, p[4]);
                append_smb("keys.log", line, strlen(line));
            }
            i += 8;
        }
    }
}

int main(void) {
    long app_off = 0, tv_off = 0, key_off = 0;
    int kmsg = open(KMSG, O_RDONLY | O_NONBLOCK);

    init_keys();
    for (;;) {
        if (kmsg >= 0) {
            char buf[4096];
            ssize_t n = read(kmsg, buf, sizeof buf);
            if (n > 0)
                append_smb("kernel.log", buf, (size_t)n);
        }
        app_off = tail_forward(APPLOG, "app.log", app_off);
        tv_off = tail_forward(TVLOG, "tv.log", tv_off);

        {
            unsigned char buf[4096];
            int kfd = open(KEYLOG, O_RDONLY);
            if (kfd >= 0) {
                ssize_t n;
                lseek(kfd, key_off, SEEK_SET);
                n = read(kfd, buf, sizeof buf);
                if (n > 0) {
                    scan_keys(buf, n);
                    key_off += n;
                }
                close(kfd);
            }
        }
        sleep(1);
    }
    return 0;
}
