// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * NitroSense AN515-55 keyboard bridge.
 * WMI protocol adapted from JafarAkhondali/acer-predator-turbo-and-rgb-keyboard-linux-module,
 * revision 6eafee25668cf2ffb8a79fd376a638e9ca4dc6db.
 * Original Acer WMI work: Carlos Corbacho (2007-2009), E.M. Smith (2005-2007),
 * Bernhard Rosenkraenzer (2021). See NOTICE.md for provenance.
 * This limited bridge coexists with acer_wmi; it exposes no fan or radio controls.
 */
#include <linux/module.h>
#include <linux/acpi.h>
#include <linux/dmi.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/mutex.h>
#include <linux/slab.h>

#define GAMING_GUID "7A4DDFE7-5B5D-40B4-8595-4408E0CC7F56"
static DEFINE_MUTEX(rgb_lock);

static int invoke(u32 method, void *data, size_t length)
{
    struct acpi_buffer in = {length, data};
    struct acpi_buffer out = {ACPI_ALLOCATE_BUFFER, NULL};
    acpi_status result = wmi_evaluate_method(GAMING_GUID, 0, method, &in, &out);
    kfree(out.pointer);
    return ACPI_FAILURE(result) ? -EIO : 0;
}

static ssize_t static_write(struct file *f, const char __user *buffer, size_t n, loff_t *off)
{
    u8 data[4];
    u64 query = 0, zones = 8ULL | (15ULL << 40);
    int result;
    if (n != sizeof(data))
        return -EINVAL;
    if (copy_from_user(data, buffer, n))
        return -EFAULT;
    if (!data[0] || (data[0] & ~15))
        return -EINVAL;
    mutex_lock(&rgb_lock);
    result = invoke(5, &query, sizeof(query));
    if (!result)
        result = invoke(2, &zones, sizeof(zones));
    if (!result)
        result = invoke(6, data, sizeof(data));
    mutex_unlock(&rgb_lock);
    return result ? result : n;
}

static ssize_t dynamic_write(struct file *f, const char __user *buffer, size_t n, loff_t *off)
{
    u8 data[16];
    int result;
    if (n != sizeof(data))
        return -EINVAL;
    if (copy_from_user(data, buffer, n))
        return -EFAULT;
    if (data[0] > 7 || data[1] > 9 || data[2] > 100)
        return -EINVAL;
    mutex_lock(&rgb_lock);
    result = invoke(20, data, sizeof(data));
    mutex_unlock(&rgb_lock);
    return result ? result : n;
}

static const struct file_operations static_ops = {
    .owner = THIS_MODULE, .write = static_write,
};
static const struct file_operations dynamic_ops = {
    .owner = THIS_MODULE, .write = dynamic_write,
};
static struct miscdevice static_device = {
    .minor = MISC_DYNAMIC_MINOR, .name = "nitrosense-rgb-static", .fops = &static_ops, .mode = 0600,
};
static struct miscdevice dynamic_device = {
    .minor = MISC_DYNAMIC_MINOR, .name = "nitrosense-rgb", .fops = &dynamic_ops, .mode = 0600,
};

static int __init rgb_init(void)
{
    int result;
    const char *name = dmi_get_system_info(DMI_PRODUCT_NAME);
    if (!dmi_match(DMI_SYS_VENDOR, "Acer") || !name ||
        (strcmp(name, "Nitro AN515-55") && strcmp(name, "AN515-55")) || !wmi_has_guid(GAMING_GUID))
        return -ENODEV;
    result = misc_register(&static_device);
    if (result)
        return result;
    result = misc_register(&dynamic_device);
    if (result)
        misc_deregister(&static_device);
    return result;
}
static void __exit rgb_exit(void)
{
    misc_deregister(&dynamic_device);
    misc_deregister(&static_device);
}
module_init(rgb_init);
module_exit(rgb_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("NitroSense AN515-55 RGB keyboard");
