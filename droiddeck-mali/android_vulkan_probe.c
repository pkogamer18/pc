/*
 * DroidDeck Z2464N host Vulkan probe. Standalone Android arm64 executable.
 * No root, APK, guest rootfs or Adreno/Turnip driver required.
 * Compile with Android NDK: aarch64-linux-android26-clang -std=c11 -Wall -Wextra
 *   -O2 android_vulkan_probe.c -o android-vulkan-probe -lvulkan
 */
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

static void print_exts(VkPhysicalDevice gpu) {
    uint32_t n = 0;
    VkResult r = vkEnumerateDeviceExtensionProperties(gpu, NULL, &n, NULL);
    if (r != VK_SUCCESS || n > 4096) {
        printf("device_extensions_error=%d count=%u\n", r, n);
        return;
    }
    VkExtensionProperties e[4096];
    r = vkEnumerateDeviceExtensionProperties(gpu, NULL, &n, e);
    if (r != VK_SUCCESS && r != VK_INCOMPLETE) {
        printf("device_extensions_error=%d\n", r);
        return;
    }
    static const char *wanted[] = {
        "VK_KHR_swapchain", "VK_KHR_external_memory",
        "VK_KHR_external_memory_fd", "VK_ANDROID_external_memory_android_hardware_buffer",
        "VK_KHR_external_semaphore", "VK_KHR_external_semaphore_fd",
        "VK_KHR_timeline_semaphore", "VK_KHR_synchronization2",
        "VK_EXT_external_memory_dma_buf", "VK_EXT_image_drm_format_modifier",
        "VK_EXT_descriptor_indexing", "VK_KHR_buffer_device_address",
        "VK_EXT_robustness2", "VK_KHR_dynamic_rendering"
    };
    for (size_t j = 0; j < sizeof(wanted)/sizeof(wanted[0]); ++j) {
        int present = 0;
        for (uint32_t i = 0; i < n; ++i)
            if (!strcmp(e[i].extensionName, wanted[j])) { present = 1; break; }
        printf("extension.%s=%s\n", wanted[j], present ? "yes" : "no");
    }
    printf("device_extension_count=%u\n", n);
}

int main(void) {
    printf("droiddeck_host_vulkan_probe=1\n");
    VkApplicationInfo app = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "DroidDeck Mali Probe", .apiVersion = VK_API_VERSION_1_0 };
    VkInstanceCreateInfo ci = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &app };
    VkInstance instance = VK_NULL_HANDLE;
    VkResult r = vkCreateInstance(&ci, NULL, &instance);
    printf("vkCreateInstance=%d\n", r);
    if (r != VK_SUCCESS) return 2;
    uint32_t n = 0;
    r = vkEnumeratePhysicalDevices(instance, &n, NULL);
    printf("vkEnumeratePhysicalDevices=%d count=%u\n", r, n);
    if (r != VK_SUCCESS || !n || n > 16) { vkDestroyInstance(instance, NULL); return 3; }
    VkPhysicalDevice devices[16];
    r = vkEnumeratePhysicalDevices(instance, &n, devices);
    if (r != VK_SUCCESS && r != VK_INCOMPLETE) { vkDestroyInstance(instance, NULL); return 4; }
    for (uint32_t i = 0; i < n; ++i) {
        VkPhysicalDeviceProperties p;
        VkPhysicalDeviceFeatures f;
        VkPhysicalDeviceMemoryProperties m;
        vkGetPhysicalDeviceProperties(devices[i], &p);
        vkGetPhysicalDeviceFeatures(devices[i], &f);
        vkGetPhysicalDeviceMemoryProperties(devices[i], &m);
        printf("gpu[%u].name=%s\n", i, p.deviceName);
        printf("gpu[%u].vendor_id=0x%04x device_id=0x%04x\n", i, p.vendorID, p.deviceID);
        printf("gpu[%u].api=%u.%u.%u driver_version=%u\n", i,
            VK_VERSION_MAJOR(p.apiVersion), VK_VERSION_MINOR(p.apiVersion),
            VK_VERSION_PATCH(p.apiVersion), p.driverVersion);
        printf("gpu[%u].type=%u max_image_2d=%u\n", i, p.deviceType, p.limits.maxImageDimension2D);
        printf("gpu[%u].features.bc=%u etc2=%u astc_ldr=%u\n", i,
            f.textureCompressionBC, f.textureCompressionETC2, f.textureCompressionASTC_LDR);
        printf("gpu[%u].memory_heaps=%u memory_types=%u\n", i, m.memoryHeapCount, m.memoryTypeCount);
        uint32_t qn = 0;
        vkGetPhysicalDeviceQueueFamilyProperties(devices[i], &qn, NULL);
        if (qn > 32) qn = 32;
        VkQueueFamilyProperties qs[32];
        vkGetPhysicalDeviceQueueFamilyProperties(devices[i], &qn, qs);
        for (uint32_t q = 0; q < qn; ++q)
            printf("gpu[%u].queue[%u].flags=0x%x count=%u\n", i, q, qs[q].queueFlags, qs[q].queueCount);
        print_exts(devices[i]);
        /* Confirm that the vendor ICD can create a usable hardware Vulkan device,
         * not just enumerate physical devices. No window or root required. */
        int graphics_family = -1;
        for (uint32_t q = 0; q < qn; ++q) {
            if (qs[q].queueCount && (qs[q].queueFlags & VK_QUEUE_GRAPHICS_BIT)) {
                graphics_family = (int)q;
                break;
            }
        }
        printf("gpu[%u].graphics_queue_family=%d\n", i, graphics_family);
        if (graphics_family >= 0) {
            const float priority = 1.0f;
            VkDeviceQueueCreateInfo qi = {
                .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
                .queueFamilyIndex = (uint32_t)graphics_family,
                .queueCount = 1,
                .pQueuePriorities = &priority
            };
            VkDeviceCreateInfo di = {
                .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
                .queueCreateInfoCount = 1,
                .pQueueCreateInfos = &qi
            };
            VkDevice device = VK_NULL_HANDLE;
            VkResult dr = vkCreateDevice(devices[i], &di, NULL, &device);
            printf("gpu[%u].vkCreateDevice=%d\n", i, dr);
            if (dr == VK_SUCCESS) {
                VkQueue queue = VK_NULL_HANDLE;
                vkGetDeviceQueue(device, (uint32_t)graphics_family, 0, &queue);
                printf("gpu[%u].graphics_queue_available=%s\n", i, queue != VK_NULL_HANDLE ? "yes" : "no");
                VkResult idle = vkDeviceWaitIdle(device);
                printf("gpu[%u].vkDeviceWaitIdle=%d\n", i, idle);
                vkDestroyDevice(device, NULL);
            }
        }

    }
    vkDestroyInstance(instance, NULL);
    return 0;
}
