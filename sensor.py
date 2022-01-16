import logging
from datetime import date, datetime, timedelta
from typing import NamedTuple

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_DATE, CONF_RESOURCES
from homeassistant.helpers.entity import Entity

DOMAIN = 'waste'

__version__ = '0.0.1'

_LOGGER = logging.getLogger(__name__)

ATTR_TRASHTYPE = 'trash_type'

CONF_TRASH_DAY = "trash_day"
CONF_GREEN_DAY = "green_day"
CONF_GREEN_WEEK = "green_week"
CONF_GREEN_SEASON_START = "green_season_start"
CONF_GREEN_SEASON_END = "green_season_end"
CONF_GREEN_OFF_SEASON_DAYS = "green_off_season_days"

SENSOR_TYPES = {
    'today': ['Today', 'mdi:recycle'],
    'tomorrow': ['Tomorrow', 'mdi:recycle'],
    'trash': ['Trash', 'mdi:recycle'],
    'green': ['Green', 'mdi:recycle']
}

WEEK_TYPES = {
    'odd',
    'even'
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_TRASH_DAY): vol.Range(0,6),
    vol.Required(CONF_GREEN_DAY): vol.Range(0,6),
    vol.Required(CONF_GREEN_WEEK): vol.In(WEEK_TYPES),
    vol.Optional(CONF_GREEN_SEASON_START, default=1): vol.Range(1,12),
    vol.Optional(CONF_GREEN_SEASON_END, default=12): vol.Range(1,12),
    vol.Optional(CONF_GREEN_OFF_SEASON_DAYS, default=[]): vol.All(
        cv.ensure_list, [cv.date]
    )
})

#    trash_day: thusday
#    green_day: friday
#    green_week: odd
#    green_days: [2018-12-7, 2019-1-5, 2019-2-1, 2019-3-1, 2019-3-29]
#    green_season_start: 4
#    green_season_ends: 11


def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.debug("Setting up Waste API...")

    trash_day = config.get(CONF_TRASH_DAY)
    green_day = config.get(CONF_GREEN_DAY)
    green_week = config.get(CONF_GREEN_WEEK)
    green_season_start = config.get(CONF_GREEN_SEASON_START)
    green_season_end = config.get(CONF_GREEN_SEASON_END)
    green_off_season_dates = []
    for date in config.get(CONF_GREEN_OFF_SEASON_DAYS):
        green_off_season_dates.append(date)
    api = WasteApi(trash_day, green_day, green_week, green_season_start, green_season_end, green_off_season_dates)

    entities = []

    for resource in config.get(CONF_RESOURCES):
        if resource == 'today':
            entities.append(TodayWasteSensor(api))
        elif resource == 'tomorrow':
            entities.append(TomorrowWasteSensor(api))
        else:
            entities.append(WasteTypeSensor(api, resource))

    add_entities(entities)


WasteSchedule = NamedTuple('WasteSchedule', [('trash_type', str), ('pickup_date', date)])

class WasteApi:

    def __init__(self, trash_day, green_day, green_week, green_season_start, green_season_end, green_off_season_dates):
        self._trash_day = trash_day
        self._green_day = green_day
        self._green_week = green_week
        self._green_season_start = green_season_start
        self._green_season_end = green_season_end
        self._green_off_season_dates = green_off_season_dates

    def next_collection_on(self, collection_day, date):
        day_of_week = date.weekday()
        if day_of_week < collection_day:
            return date - timedelta(days=day_of_week - (collection_day - 1))
        else:
            return date + timedelta(days=(collection_day + 6) - day_of_week)

    def trash_collection_day(self, date):
        return self.next_collection_on(self._trash_day, date)

    def green_noseason_day(self, date):
        index = 0
        while index < len(self._green_off_season_dates):
            noseason_day = self._green_off_season_dates[index]
            index += 1
            if date <= noseason_day:
                return noseason_day
        return None

    def green_collection_day(self, date):
        day = None
        if date.month < self._green_season_start or date.month > self._green_season_end:
            day = self.green_noseason_day(date)
        if day is None:
            day = self.next_collection_on(self._green_day, date)
            week_number_mod = day.isocalendar()[1] % 2
            if (self._green_week == "odd" and week_number_mod == 0) or (self._green_week == "even" and week_number_mod == 1):
                day = day + timedelta(weeks=1)
            if day.month < self._green_season_start or day.month > self._green_season_end:
                day = self.green_noseason_day(date)
        return day

    def next_collection_of(self, type):
        today = datetime.now().date()
        if type == "trash":
            return WasteSchedule(type, self.trash_collection_day(today))
        elif type == "green":
            return WasteSchedule(type, self.green_collection_day(today))
        else:
            return None

    def collection_on(self, date):
        if self.trash_collection_day(date) == date:
            return WasteSchedule("trash", date)
        if self.green_collection_day(date) == date:
            return WasteSchedule("green", date)
        return None

    def collection_today(self):
        today = datetime.now().date()
        return self.collection_on(today)

    def collection_tomorrow(self):
        tomorrow = datetime.now().date() + timedelta(days=1)
        return self.collection_on(tomorrow)


class AbstractWasteSensor(Entity):

    def __init__(self, api, sensor_type):
        self._api = api
        self._schedule = None
        self._name = "Waste {}".format(SENSOR_TYPES[sensor_type][0])
        self._icon = SENSOR_TYPES[sensor_type][1]
        self._date = None

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        if not self._schedule:
            return None

        if not self._schedule.pickup_date:
            return None

        return self._schedule.pickup_date.strftime('%Y-%m-%d')

    @property
    def device_state_attributes(self):
        if not self._schedule:
            if not self._date:
                return None
            return { ATTR_DATE: self._date.strftime('%Y-%m-%d') }

        return {
            ATTR_DATE: self._schedule.pickup_date.strftime('%Y-%m-%d'),
            ATTR_TRASHTYPE: self._schedule.trash_type
        }


class WasteTypeSensor(AbstractWasteSensor):

    def __init__(self, api, trash_type):
        super().__init__(api, trash_type)
        self._trash_type = trash_type

    def update(self):
        self._schedule = self._api.next_collection_of(self._trash_type)


class TodayWasteSensor(AbstractWasteSensor):

    def __init__(self, api):
        super().__init__(api, 'today')

    def update(self):
        self._schedule = self._api.collection_today()
        self._date = datetime.now().date()

    @property
    def state(self):
        if self._schedule is None:
            return 'None'

        return SENSOR_TYPES[self._schedule.trash_type.lower()][0]


class TomorrowWasteSensor(AbstractWasteSensor):

    def __init__(self, api):
        super().__init__(api, 'tomorrow')

    def update(self):
        self._schedule = self._api.collection_tomorrow()
        self._date = datetime.now().date() + timedelta(days=1)

    @property
    def state(self):
        if self._schedule is None:
            return 'None'

        return SENSOR_TYPES[self._schedule.trash_type.lower()][0]