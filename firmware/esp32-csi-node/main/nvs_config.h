#ifndef NVS_CONFIG_H
#define NVS_CONFIG_H

#include <stdint.h>

#define NVS_CFG_SSID_MAX 33
#define NVS_CFG_PASS_MAX 65
#define NVS_CFG_IP_MAX   16

typedef struct {
    char     wifi_ssid[NVS_CFG_SSID_MAX];
    char     wifi_password[NVS_CFG_PASS_MAX];
    char     target_ip[NVS_CFG_IP_MAX];
    uint16_t target_port;
    uint8_t  node_id;
} nvs_config_t;

void nvs_config_load(nvs_config_t *cfg);

#endif
