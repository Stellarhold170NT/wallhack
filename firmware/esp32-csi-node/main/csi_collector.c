#include "csi_collector.h"
#include <string.h>
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_timer.h"
#include "stream_sender.h"

#ifndef CONFIG_ESP_WIFI_CSI_ENABLED
#error "CONFIG_ESP_WIFI_CSI_ENABLED must be set in sdkconfig."
#endif

static const char *TAG = "csi_collector";
static uint8_t  s_node_id = 1;
static uint32_t s_sequence = 0;
static uint32_t s_cb_count = 0;
static uint32_t s_send_ok = 0;
static uint32_t s_send_fail = 0;

#define CSI_MIN_SEND_INTERVAL_US (20 * 1000)  // 20ms = 50Hz
static int64_t s_last_send_us = 0;

static uint32_t derive_freq_mhz(uint8_t channel)
{
    if (channel >= 1 && channel <= 13) {
        return 2412 + (channel - 1) * 5;
    } else if (channel == 14) {
        return 2484;
    } else if (channel >= 36 && channel <= 177) {
        return 5000 + channel * 5;
    }
    return 0;
}

size_t csi_serialize_frame(const wifi_csi_info_t *info, uint8_t *buf, size_t buf_len)
{
    if (info == NULL || buf == NULL || info->buf == NULL) {
        ESP_LOGW(TAG, "serialize: null input");
        return 0;
    }

    uint16_t iq_len = info->len;
    uint16_t n_subcarriers = iq_len / 2;
    size_t frame_size = CSI_HEADER_SIZE + iq_len;

    if (frame_size > buf_len) {
        ESP_LOGW(TAG, "serialize: frame %d > buf %d", (int)frame_size, (int)buf_len);
        return 0;
    }

    uint32_t freq_mhz = derive_freq_mhz(info->rx_ctrl.channel);
    uint32_t seq = s_sequence++;

    // Write header (little-endian)
    buf[0] = (CSI_MAGIC >>  0) & 0xFF;
    buf[1] = (CSI_MAGIC >>  8) & 0xFF;
    buf[2] = (CSI_MAGIC >> 16) & 0xFF;
    buf[3] = (CSI_MAGIC >> 24) & 0xFF;
    buf[4] = s_node_id;
    buf[5] = 1;
    buf[6] = n_subcarriers & 0xFF;
    buf[7] = (n_subcarriers >> 8) & 0xFF;
    buf[8] = freq_mhz & 0xFF;
    buf[9] = (freq_mhz >> 8) & 0xFF;
    buf[10] = (freq_mhz >> 16) & 0xFF;
    buf[11] = (freq_mhz >> 24) & 0xFF;
    buf[12] = seq & 0xFF;
    buf[13] = (seq >> 8) & 0xFF;
    buf[14] = (seq >> 16) & 0xFF;
    buf[15] = (seq >> 24) & 0xFF;
    buf[16] = (uint8_t)info->rx_ctrl.rssi;
    buf[17] = (uint8_t)info->rx_ctrl.noise_floor;
    buf[18] = 0;
    buf[19] = 0;

    memcpy(buf + CSI_HEADER_SIZE, info->buf, iq_len);

    return frame_size;
}

static void csi_rx_callback(void *ctx, wifi_csi_info_t *info)
{
    (void)ctx;
    s_cb_count++;

    // Rate limit to ~50 Hz
    int64_t now = esp_timer_get_time();
    if (now - s_last_send_us < CSI_MIN_SEND_INTERVAL_US) {
        return;
    }
    s_last_send_us = now;

    uint8_t frame_buf[512];
    size_t frame_len = csi_serialize_frame(info, frame_buf, sizeof(frame_buf));
    if (frame_len == 0) {
        s_send_fail++;
        return;
    }

    int rc = stream_sender_send(frame_buf, frame_len);
    if (rc < 0) {
        s_send_fail++;
    } else {
        s_send_ok++;
    }
}

void csi_collector_init(void)
{
    esp_err_t err;

    err = esp_wifi_set_promiscuous(true);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "set_promiscuous failed: %s", esp_err_to_name(err));
    }

    /*
     * CSI LTF configuration determines subcarrier count per frame:
     *   lltf_en=true           → 64 subcarriers (legacy, always present)
     *   + htltf_en=true        → +64 subcarriers (HT-LTF, 802.11n)
     *   + stbc_htltf2_en=true  → +64 subcarriers (STBC 2nd stream)
     * Actual count varies per received packet type (64/128/192).
     * Python processor now handles all counts dynamically.
     * For consistent 64-SC frames, set htltf_en=false, stbc_htltf2_en=false.
     */
    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .manu_scale = false,
        .shift = 0,
    };

    err = esp_wifi_set_csi_config(&csi_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "set_csi_config failed: %s", esp_err_to_name(err));
        return;
    }

    err = esp_wifi_set_csi_rx_cb(csi_rx_callback, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "set_csi_rx_cb failed: %s", esp_err_to_name(err));
        return;
    }

    err = esp_wifi_set_csi(true);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "set_csi failed: %s", esp_err_to_name(err));
        return;
    }

    ESP_LOGI(TAG, "CSI collector initialized, node_id=%d", s_node_id);
}

void csi_collector_set_node_id(uint8_t node_id)
{
    s_node_id = node_id;
    ESP_LOGI(TAG, "node_id set to %d", s_node_id);
}

uint8_t csi_collector_get_node_id(void)
{
    return s_node_id;
}
