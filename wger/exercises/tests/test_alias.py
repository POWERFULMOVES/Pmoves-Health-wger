# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License

# wger
from wger.core.tests.api_base_test import ExerciseCrudApiTestCase
from wger.exercises.models import Alias
from wger.exercises.tests.api_mixins import ActstreamApiMixin


class AliasCustomApiTestCase(ActstreamApiMixin, ExerciseCrudApiTestCase):
    pk = 1
    resource = Alias

    data = {
        'translation': 1,
        'alias': 'Alias 123',
    }

    def get_resource_name(self):
        return 'exercisealias'
