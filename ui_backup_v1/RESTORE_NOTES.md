# PhoneMic UI Backup (v1 Studio Archive)

This folder contains a verbatim snapshot of `app/src/main/java/com/example/ui/` captured before the flat Studio / 3-tab UI redesign (`Status`, `Home`, `Settings`).

It sits outside `app/src/main/java/` so Gradle never compiles duplicate Kotlin symbols into the APK.

## How to Restore
1. Copy the contents of `ui_backup_v1/` (`theme/`, `screens/`, `components/`) back into `app/src/main/java/com/example/ui/`.
2. Revert `MainActivity.kt` to call `PhoneMicTheme { PhoneMicScreen(viewModel = viewModel) }` if needed.
