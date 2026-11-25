
# PlatformIO extra script: merge bootloader + partition table + app
# into one firmware image that Wokwi can load.

Import("env")
from os.path import join, isfile

FS_OFFSET = None  # Ejemplo: "0x290000"

def merge_firmware(source, target, env):
    board = env.BoardConfig()
    build_dir = env.subst("$BUILD_DIR")
    merged = join(build_dir, "firmware.merged.bin")

    # Usar el ejecutable disponible en la versión instalada de esptool
    esptool = join(
        env.PioPlatform().get_package_dir("tool-esptool"),
        "esptool.exe"
    )

    images = [
        (offset, env.subst(path))
        for offset, path in env.get("FLASH_EXTRA_IMAGES", [])
    ]

    images.append((
        env.subst("$ESP32_APP_OFFSET"),
        str(target[0])
    ))

    fs_image = join(
        build_dir,
        env.subst("$ESP32_FS_IMAGE_NAME") + ".bin"
    )

    if FS_OFFSET and isfile(fs_image):
        images.append((FS_OFFSET, fs_image))

    # Ejecutar esptool directamente
    cmd = [
        '"%s"' % esptool,
        "--chip", board.get("build.mcu", "esp32"),
        "merge-bin",
        "-o", '"%s"' % merged,
        "--flash-mode", board.get("build.flash_mode", "dio"),
        "--flash-size", board.get("upload.flash_size", "4MB"),
    ]

    for offset, path in images:
        cmd += [
            offset if isinstance(offset, str) else hex(offset),
            '"%s"' % path
        ]

    env.Execute(
        env.VerboseAction(
            " ".join(cmd),
            "Merging firmware images into %s" % merged
        )
    )

env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", merge_firmware)
