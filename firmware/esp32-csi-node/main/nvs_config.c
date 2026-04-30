#include "nvs_config.h"
#include <string.h>
#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"

#define DEFAULT_WIFI_SSID     "wifi-densepose"
#define DEFAULT_WIFI_PASSWORD ""
#define DEFAULT_TARGET_IP     "192.168.1.100"
#define DEFAULT_TARGET_PORT   5005
#define DEFAULT_NODE_ID       1

static const char *TAG = "nvs_config";

void nvs_config_load(nvs_config_t *cfg) {
    strncpy(cfg->wifi_ssid, DEFAULT_WIFI_SSID, NVS_CFG_SSID_MAX - 1);
    cfg->wifi_ssid[NVS_CFG_SSID_MAX - 1] = '\0';

    strncpy(cfg->wifi_password, DEFAULT_WIFI_PASSWORD, NVS_CFG_PASS_MAX - 1);
    cfg->wifi_password[NVS_CFG_PASS_MAX - 1] = '\0';

    strncpy(cfg->target_ip, DEFAULT_TARGET_IP, NVS_CFG_IP_MAX - 1);
    cfg->target_ip[NVS_CFG_IP_MAX - 1] = '\0';

    cfg->target_port = DEFAULT_TARGET_PORT;
    cfg->node_id = DEFAULT_NODE_ID;

    nvs_handle_t handle;
    esp_err_t err = nvs_open("csi_cfg", NVS_READONLY, &handle);
    if (err != ESP_OK) {
        ESP_LOGI(TAG, "No NVS config found, using compiled defaults");
        return;
    }

    size_t len = NVS_CFG_SSID_MAX;
    if (nvs_get_str(handle, "ssid", cfg->wifi_ssid, &len) == ESP_OK) {
        ESP_LOGI(TAG, "NVS override: ssid=%s", cfg->wifi_ssid);
    }

    len = NVS_CFG_PASS_MAX;
    if (nvs_get_str(handle, "password", cfg->wifi_password, &len) == ESP_OK) {
        ESP_LOGI(TAG, "NVS override: password set");
    }

    len = NVS_CFG_IP_MAX;
    if (nvs_get_str(handle, "target_ip", cfg->target_ip, &len) == ESP_OK) {
        ESP_LOGI(TAG, "NVS override: target_ip=%s", cfg->target_ip);
    }

    uint16_t port;
    if (nvs_get_u16(handle, "target_port", &port) == ESP_OK) {
        cfg->target_port = port;
        ESP_LOGI(TAG, "NVS override: target_port=%u", cfg->target_port);
    }

    uint8_t node_id;
    if (nvs_get_u8(handle, "node_id", &node_id) == ESP_OK) {
        cfg->node_id = node_id;
        ESP_LOGI(TAG, "NVS override: node_id=%u", cfg->node_id);
    }

    nvs_close(handle);
    ESP_LOGI(TAG, "Config loaded — ssid=%s target=%s:%d node=%d",
             cfg->wifi_ssid, cfg->target_ip, cfg->target_port, cfg->node_id);
}
