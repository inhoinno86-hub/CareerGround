/* BrowserOS process-only compatibility for a hardcoded wildcard TCP listener.
 * Build as a user-owned LD_PRELOAD library; never install into system paths.
 * UDP, Unix sockets, outbound connect(), port-zero binds, and explicitly
 * addressed sockets are unchanged. Verify actual listeners after every launch.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <netinet/in.h>
#include <pthread.h>
#include <string.h>
#include <sys/socket.h>

typedef int (*bind_function)(int, const struct sockaddr *, socklen_t);
static bind_function original_bind;
static pthread_once_t initialize_once = PTHREAD_ONCE_INIT;

static void resolve_bind(void) {
    void *symbol = dlsym(RTLD_NEXT, "bind");
    memcpy(&original_bind, &symbol, sizeof(original_bind));
}

int bind(int descriptor, const struct sockaddr *address, socklen_t length) {
    pthread_once(&initialize_once, resolve_bind);
    if (original_bind == NULL) {
        errno = ENOSYS;
        return -1;
    }
    int type = 0;
    socklen_t type_length = sizeof(type);
    if (address != NULL &&
        getsockopt(descriptor, SOL_SOCKET, SO_TYPE, &type, &type_length) != 0) {
        return -1;
    }
    if (address != NULL && type == SOCK_STREAM) {
        if (address->sa_family == AF_INET && length >= sizeof(struct sockaddr_in)) {
            struct sockaddr_in local;
            memcpy(&local, address, sizeof(local));
            if (local.sin_port != 0 && local.sin_addr.s_addr == htonl(INADDR_ANY)) {
                local.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
                return original_bind(descriptor, (struct sockaddr *)&local, sizeof(local));
            }
        } else if (address->sa_family == AF_INET6 &&
                   length >= sizeof(struct sockaddr_in6)) {
            struct sockaddr_in6 local;
            memcpy(&local, address, sizeof(local));
            if (local.sin6_port != 0 && IN6_IS_ADDR_UNSPECIFIED(&local.sin6_addr)) {
                local.sin6_addr = in6addr_loopback;
                return original_bind(descriptor, (struct sockaddr *)&local, sizeof(local));
            }
        }
    }
    return original_bind(descriptor, address, length);
}
