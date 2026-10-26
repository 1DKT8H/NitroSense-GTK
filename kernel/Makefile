obj-m := nitrosense_rgb.o
KERNELDIR ?= /lib/modules/$(shell uname -r)/build
all:
	$(MAKE) -C $(KERNELDIR) M=$(CURDIR) modules
clean:
	$(MAKE) -C $(KERNELDIR) M=$(CURDIR) clean
