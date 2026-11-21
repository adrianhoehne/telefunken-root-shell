/*
 * libkeyhook.so — transparent key-capture hook for the Vestel 17MB211 TV app.
 *
 * The TV app (aurora.elf) reads remote-control events from the STBC MCU over
 * /dev/ttyS2 (115200 8N1). This library is injected via LD_PRELOAD and
 * transparently logs everything the app reads from any /dev/ttyS* fd to
 * /tmp/keylog.bin. Reads are passed through unchanged.
 *
 * IMPORTANT: open()/read() are implemented with raw syscalls (openat/read),
 * NOT via dlsym(). The dynamic linker itself calls open/read while loading,
 * and a dlsym-based hook has uninitialised function pointers at that point —
 * that crashed the app and caused a boot loop. Syscalls cannot recurse.
 *
 * Build:
 *   arm-linux-gnueabihf-gcc -shared -fPIC -O2 -o libkeyhook.so libkeyhook.c
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/stat.h>

#ifndef AT_FDCWD
#define AT_FDCWD (-100)
#endif

static int key_fd = -1;
static int log_fd = -1;

static void do_log(const void *buf, size_t len) {
    if (log_fd < 0)
        log_fd = (int)syscall(SYS_openat, AT_FDCWD, "/tmp/keylog.bin",
                              O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (log_fd >= 0)
        syscall(SYS_write, log_fd, buf, len);
}

static int fd_is_ttyS(int fd) {
    char path[64], link[256];
    snprintf(path, sizeof path, "/proc/self/fd/%d", fd);
    ssize_t n = (ssize_t)syscall(SYS_readlinkat, AT_FDCWD, path, link,
                                 sizeof link - 1);
    if (n < 0)
        return 0;
    link[n] = 0;
    return strstr(link, "ttyS") != NULL;
}

int open(const char *path, int flags, ...) {
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = va_arg(ap, mode_t);
        va_end(ap);
    }
    int fd = (int)syscall(SYS_openat, AT_FDCWD, path, flags, mode);
    if (fd >= 0 && strstr(path, "ttyS")) {
        key_fd = fd;
        do_log("\n==OPEN==", 8);
        do_log(path, strlen(path));
        do_log("==\n", 3);
    }
    return fd;
}

ssize_t read(int fd, void *buf, size_t count) {
    ssize_t r = (ssize_t)syscall(SYS_read, fd, buf, count);
    if (r > 0 && (fd == key_fd || fd_is_ttyS(fd)))
        do_log(buf, (size_t)r);
    return r;
}
