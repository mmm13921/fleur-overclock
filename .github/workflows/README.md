# GitHub Actions Workflows

Workflows are separated by purpose/profile. Prefer the dedicated profile workflow over changing the generic Fleux workflow.

- `build-walt-mt6781.yml`: WALT MT6781 profile.
- `build-hmp-hybrid-mt6781.yml`: HMP/Hybrid profile.
- `build-capacity-margin-0.yml`: capacity-margin test profile.
- `build-v11-hmp-projectid.yml`, `build-v12-android-data.yml`, `build-v12-stability.yml`: pinned V11/V12 profiles.
- `build-modem-resume-test.yml`: modem resume comparison profile.
- `release-oc*.yml`: overclock release profiles.

A green workflow confirms only the checks performed by that workflow. Device boot/runtime validation must be recorded separately.
