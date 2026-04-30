#include "stream_sender.h"
#include <string.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"

#define DEFAULT_TARGET_IP   "192.168.1.100"
#define DEFAULT_TARGET_PORT 5005

static const char *TAG = "stream_sender";
static int s_sock = -1;
static struct sockaddr_in s_dest_addr;
static int64_t s_backoff_until_us = 0;
#define ENOMEM_COOLDOWN_MS 100
static uint32_t s_enomem_suppressed = 0;

static int sender_init_internal(const char *ip, uint16_t port)
{
    s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s_sock < 0) {
        ESP_LOGE(TAG, "Failed to create socket: errno %d", errno);
        return -1;
    }

    memset(&s_dest_addr, 0, sizeof(s_dest_addr));
    s_dest_addr.sin_family = AF_INET;
    s_dest_addr.sin_port = htons(port);

    if (inet_pton(AF_INET, ip, &s_dest_addr.sin_addr) <= 0) {
        ESP_LOGE(TAG, "Invalid target IP: %s", ip);
        close(s_sock);
        s_sock = -1;
        return -1;
    }

    ESP_LOGI(TAG, "UDP sender initialized: %s:%d", ip, port);
    return 0;
}

int stream_sender_init(void)
{
    return sender_init_internal(DEFAULT_TARGET_IP, DEFAULT_TARGET_PORT);
}

int stream_sender_init_with(const char *ip, uint16_t port)
{
    return sender_init_internal(ip, port);
}

int stream_sender_send(const uint8_t *data, size_t len)
{
    if (s_sock < 0) {
        return -1;
    }

    if (s_backoff_until_us > 0) {
        int64_t now = esp_timer_get_time();
        if (now < s_backoff_until_us) {
            s_enomem_suppressed++;
            return -1;
        }
        ESP_LOGI(TAG, "ENOMEM backoff expired, resuming sends (%lu suppressed)",
                 (unsigned long)s_enomem_suppressed);
        s_backoff_until_us = 0;
        s_enomem_suppressed = 0;
    }

    int sent = sendto(s_sock, data, len, 0,
                      (struct sockaddr *)&s_dest_addr, sizeof(s_dest_addr));
    if (sent < 0) {
        if (errno == ENOMEM) {
            s_backoff_until_us = esp_timer_get_time() + (int64_t)ENOMEM_COOLDOWN_MS * 1000;
            ESP_LOGW(TAG, "sendto ENOMEM — backing off for %d ms", ENOMEM_COOLDOWN_MS);
        } else {
            ESP_LOGE(TAG, "sendto failed: errno %d", errno);
        }
        return -1;
    }
    return sent;
}

void stream_sender_deinit(void)
{
    if (s_sock >= 0) {
        close(s_sock);
        s_sock = -1;
    }
}
