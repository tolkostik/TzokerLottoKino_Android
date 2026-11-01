[app]
title = Tzoker Lotto Kino
package.name = tzokerlottokino
package.domain = gr.tyxeroi
source.dir = .
source.include_exts = py
source.exclude_dirs = .github, bin, .buildozer
version = 2.0
requirements = python3,kivy==2.3.1,certifi,android
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.gradle_dependencies = com.google.android.gms:play-services-code-scanner:16.1.0, com.google.android.gms:play-services-base:18.5.0
android.meta_data = com.google.mlkit.vision.DEPENDENCIES=barcode_ui
android.enable_androidx = True
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
