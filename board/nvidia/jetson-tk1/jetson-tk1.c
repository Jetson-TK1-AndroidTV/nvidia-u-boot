/*
 * (C) Copyright 2014
 * NVIDIA Corporation <www.nvidia.com>
 *
 * SPDX-License-Identifier:     GPL-2.0+
 */

#include <common.h>
#include <netdev.h>
#include <power/as3722.h>

#include <asm/arch/gpio.h>
#include <asm/arch/pinmux.h>

DECLARE_GLOBAL_DATA_PTR;

#include <asm/gpio.h>
#include "pinmux-config-jetson-tk1.h"

#define KEY_RECOVERY_GPIO GPIO_PI1

/*
 * Routine: pinmux_init
 * Description: Do individual peripheral pinmux configs
 */
void pinmux_init(void)
{
	gpio_config_table(jetson_tk1_gpio_inits,
			  ARRAY_SIZE(jetson_tk1_gpio_inits));

	pinmux_config_pingrp_table(jetson_tk1_pingrps,
				   ARRAY_SIZE(jetson_tk1_pingrps));

	pinmux_config_drvgrp_table(jetson_tk1_drvgrps,
				   ARRAY_SIZE(jetson_tk1_drvgrps));
}

#ifdef CONFIG_PCI_TEGRA
int tegra_pcie_board_init(void)
{
	struct as3722 *pmic;
	int err;

	err = as3722_init(&pmic, gd->fdt_blob);
	if (err) {
		error("failed to initialize AS3722 PMIC: %d\n", err);
		return err;
	}

	err = as3722_sd_enable(pmic, 4);
	if (err < 0) {
		error("failed to enable SD4: %d\n", err);
		return err;
	}

	err = as3722_sd_set_voltage(pmic, 4, 0x24);
	if (err < 0) {
		error("failed to set SD4 voltage: %d\n", err);
		return err;
	}

	return 0;
}

int board_eth_init(bd_t *bis)
{
	return pci_eth_init(bis);
}
#endif /* PCI */

#ifdef CONFIG_MISC_INIT_R
int misc_init_r(void)
{
	int bootdelay = 2;
	int abort = 0;
	unsigned long ts;

	/* Get GPIOs */
	gpio_request(KEY_RECOVERY_GPIO, "recovery_btn");

	printf("Checking for recovery ...\n");
	/* delay 1000 ms */
	while ((bootdelay > 0) && (!abort)) {
		--bootdelay;
		/* delay 1000 ms */
		ts = get_timer(0);
		do {
			/* check for FORCE_RECOVERY button */
			if (!gpio_get_value(KEY_RECOVERY_GPIO)) {
				printf("\n*** RECOVERY BUTTON ***");
				setenv("recovery", "1");
				abort = 1;
			}
			udelay(10000);
		} while (!abort && get_timer(ts) < 1000);
		printf(".");
	}
	printf("\n");

	/* Free GPIOs */
	gpio_free(KEY_RECOVERY_GPIO);

	return 0;
}
#endif
