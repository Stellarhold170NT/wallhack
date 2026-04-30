#ifndef CSI_COLLECTOR_H
#define CSI_COLLECTOR_H

#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"
#include "esp_wifi_types.h"

#define CSI_MAGIC 0xC5110001
#define CSI_HEADER_SIZE 20

void csi_collector_init(void);
void csi_collector_set_node_id(uint8_t node_id);
uint8_t csi_collector_get_node_id(void);
size_t csi_serialize_frame(const wifi_csi_info_t *info, uint8_t *buf, size_t buf_len);

#endif
