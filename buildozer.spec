[app]
title = Mini Albion
package.name = minialbion
package.domain = org.example
source.dir = .
source.include_exts = py
version = 0.1
requirements = python3,kivy
orientation = landscape
fullscreen = 1

[buildozer]
log_level = 2
warn_on_root = 1

# Android
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
