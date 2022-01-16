# hass_ozo_waste
Home Assistant waste sensor of OZO Ostrava

Configuration file:
```
- platform: waste
  trash_day: 4
  green_day: 5
  green_week: odd
  green_off_season_days: [2020-12-4, 2020-12-31, 2021-1-22, 2021-2-19, 2021-3-19]
  green_season_start: 4
  green_season_end: 11
  resources:
    - today
    - tomorrow
    - green
    - trash
 ```
