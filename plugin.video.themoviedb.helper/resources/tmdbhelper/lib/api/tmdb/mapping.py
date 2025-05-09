from tmdbhelper.lib.files.ftools import cached_property
from jurialmunkey.parser import try_int, try_float, dict_to_list, get_params, IterProps
from tmdbhelper.lib.api.mapping import UPDATE_BASEKEY, _ItemMapper, get_empty_item
from tmdbhelper.lib.addon.plugin import get_mpaa_prefix, get_language, convert_type, get_setting, get_localized
from tmdbhelper.lib.addon.consts import ITER_PROPS_MAX


class ItemMapperMethods:

    @cached_property
    def tmdb_imagepath(self):
        from tmdbhelper.lib.api.tmdb.images import TMDbImagePath
        return TMDbImagePath()

    @cached_property
    def iter_props(self):
        return IterProps(ITER_PROPS_MAX).iter_props

    """
    RUNTIME
    """

    @staticmethod
    def get_runtime(v, *args, **kwargs):
        if isinstance(v, list):
            v = v[0]
        return try_int(v) * 60

    """
    COLLECTION
    """

    def get_collection(self, v):
        infoproperties = {}
        infoproperties['set.tmdb_id'] = v.get('id')
        infoproperties['set.name'] = v.get('name')
        infoproperties['set.poster'] = self.tmdb_imagepath.get_imagepath_poster(v.get('poster_path'))
        infoproperties['set.fanart'] = self.tmdb_imagepath.get_imagepath_fanart(v.get('backdrop_path'))
        return infoproperties

    def get_collection_properties(self, v):
        ratings = []
        infoproperties = {}
        year_l, year_h, votes = 9999, 0, 0
        genres = set()
        for p, i in enumerate(v, start=1):
            genre = self.get_genres_by_id(i.get('genre_ids'))
            genres.update(genre)

            infoproperties[f'set.{p}.genre'] = ' / '.join(genre)
            infoproperties[f'set.{p}.title'] = i.get('title', '')
            infoproperties[f'set.{p}.tmdb_id'] = i.get('id', '')
            infoproperties[f'set.{p}.originaltitle'] = i.get('original_title', '')
            infoproperties[f'set.{p}.plot'] = i.get('overview', '')
            infoproperties[f'set.{p}.premiered'] = i.get('release_date', '')
            infoproperties[f'set.{p}.year'] = i.get('release_date', '')[:4]
            infoproperties[f'set.{p}.rating'] = f'{try_float(i.get("vote_average")):0,.1f}'
            infoproperties[f'set.{p}.votes'] = i.get('vote_count', '')
            infoproperties[f'set.{p}.poster'] = self.tmdb_imagepath.get_imagepath_poster(i.get('poster_path', ''))
            infoproperties[f'set.{p}.fanart'] = self.tmdb_imagepath.get_imagepath_fanart(i.get('backdrop_path', ''))

            year_l = min(try_int(i.get('release_date', '')[:4]), year_l)
            year_h = max(try_int(i.get('release_date', '')[:4]), year_h)
            if i.get('vote_average'):
                ratings.append(i['vote_average'])
            votes += try_int(i.get('vote_count', 0))
        if year_l == 9999:
            year_l = None
        if year_l:
            infoproperties['set.year.first'] = year_l
        if year_h:
            infoproperties['set.year.last'] = year_h
        if year_l and year_h:
            infoproperties['set.years'] = f'{year_l} - {year_h}'
        if len(ratings):
            infoproperties['set.rating'] = infoproperties['tmdb_rating'] = f'{sum(ratings) / len(ratings):0,.1f}'
        if votes:
            infoproperties['set.votes'] = infoproperties['tmdb_votes'] = f'{votes:0,.0f}'
        if genres:
            infoproperties['set.genres'] = ' / '.join(genres)
        infoproperties['set.numitems'] = p
        return infoproperties

    """
    MPAA
    """

    @staticmethod
    def get_mpaa_rating(v, mpaa_prefix, iso_country, certification=True):
        for i in v or []:
            if not i.get('iso_3166_1') or i.get('iso_3166_1') != iso_country:
                continue
            if not certification:
                if i.get('rating'):
                    return f'{mpaa_prefix}{i["rating"]}'
                continue
            for i in sorted(i.get('release_dates', []), key=lambda k: k.get('type')):
                if i.get('certification'):
                    return f'{mpaa_prefix}{i["certification"]}'

    """
    RELEASE TYPES
    """

    @staticmethod
    def get_release_types(v, iso_country):
        from tmdbhelper.lib.addon.tmdate import is_future_timestamp
        infoproperties = {}
        info_release_types = []
        tmdb_release_types = {1: 'Premiere', 2: 'Limited', 3: 'Theatrical', 4: 'Digital', 5: 'Physical', 6: 'TV'}
        for i in v or []:
            if not i.get('iso_3166_1') or i.get('iso_3166_1') != iso_country:
                continue
            for i in sorted(i.get('release_dates', []), key=lambda k: k.get('type')):
                try:
                    rt = tmdb_release_types[i['type']]
                    rd = i['release_date'][:10]
                except (KeyError, TypeError, AttributeError):
                    continue
                if not rt or not rd:
                    continue
                infoproperties[f"{rt.lower()}_release"] = rd
                if not is_future_timestamp(rd, time_fmt="%Y-%m-%d", time_lim=10):
                    info_release_types.append(rt)
        if info_release_types:
            infoproperties['available_releases'] = ' / '.join(info_release_types)
        return infoproperties

    """
    ITER PROPS
    """

    def get_iter_props(self, v, base_name, *args, **kwargs):
        infoproperties = {}
        if kwargs.get('sorted'):
            v = sorted(v, **kwargs['sorted'])
        if kwargs.get('basic_keys'):
            infoproperties = self.iter_props(
                v, base_name, infoproperties, **kwargs['basic_keys'])
        if kwargs.get('image_keys'):
            infoproperties = self.iter_props(
                v, base_name, infoproperties, func=self.tmdb_imagepath.get_imagepath_poster, **kwargs['image_keys'])
        if kwargs.get('fanart_keys'):
            infoproperties = self.iter_props(
                v, base_name, infoproperties, func=self.tmdb_imagepath.get_imagepath_fanart, **kwargs['fanart_keys'])
        if kwargs.get('negativeimage_keys'):
            infoproperties = self.iter_props(
                v, base_name, infoproperties, func=self.tmdb_imagepath.get_imagepath_negate, **kwargs['negativeimage_keys'])
        return infoproperties

    """
    PROVIDER
    """

    def get_providers(self, v, allowlist=None):
        infoproperties = {}
        infoproperties['provider.link'] = v.pop('link', None)
        newlist = (
            dict(i, **{'key': key}) for key, value in v.items() if isinstance(value, list)
            for i in value if isinstance(i, dict))
        added = []
        added_append = added.append
        for i in sorted(newlist, key=lambda k: k.get('display_priority', 1000)):
            if not i.get('provider_name'):
                continue
            if allowlist and i['provider_name'] not in allowlist:
                continue
            # If provider already added just update type
            if i['provider_name'] in added:
                idx = f'provider.{added.index(i["provider_name"]) + 1}.type'
                infoproperties[idx] = f'{infoproperties.get(idx)} / {i.get("key")}'
                continue
            # Add item provider
            x = len(added) + 1
            infoproperties.update({
                f'provider.{x}.id': i.get('provider_id'),
                f'provider.{x}.type': i.get('key'),
                f'provider.{x}.name': i['provider_name'],
                f'provider.{x}.icon': self.tmdb_imagepath.get_imagepath_clogos(i.get('logo_path'))})
            added_append(i['provider_name'])
        infoproperties['providers'] = ' / '.join(added)
        return infoproperties

    """
    TRAILER
    """

    @staticmethod
    def get_trailer(v, iso_639_1=None):
        if not isinstance(v, dict):
            return
        url = None
        for i in v.get('results') or []:
            if i.get('type', '') != 'Trailer' or i.get('site', '') != 'YouTube' or not i.get('key'):
                continue
            if i.get('iso_639_1') == iso_639_1:
                return f'plugin://plugin.video.youtube/play/?video_id={i["key"]}'
            url = url or f'plugin://plugin.video.youtube/play/?video_id={i["key"]}'
        return url

    """
    ID
    """

    @staticmethod
    def get_external_ids(v):

        def get_key_name(key):
            if key == 'id':
                return 'tmdb'
            if key.endswith('_id'):
                return key[:-3]
            return key

        unique_ids = {get_key_name(key): value for key, value in v.items() if key and value}
        return unique_ids

    """
    PERSON
    """

    @staticmethod
    def get_roles(v, key='character'):
        infoproperties = {}
        episode_count = 0
        for x, i in enumerate(sorted(v, key=lambda d: d.get('episode_count', 0)), start=1):
            episode_count += i.get('episode_count') or 0
            infoproperties[f'{key}.{x}.name'] = i.get(key)
            infoproperties[f'{key}.{x}.episodes'] = i.get('episode_count')
            infoproperties[f'{key}.{x}.id'] = i.get('credit_id')
        else:
            infoproperties['episodes'] = episode_count
            infoproperties[key] = infoproperties['role'] = infoproperties[f'{key}.1.name']
        return infoproperties

    @staticmethod
    def get_credits(v):
        infolabels = {}
        infolabels['director'] = [
            i['name'] for i in v.get('crew', []) if i.get('name') and i.get('job') == 'Director']
        infolabels['writer'] = [
            i['name'] for i in v.get('crew', []) if i.get('name') and i.get('department') == 'Writing']
        return infolabels

    """
    ART
    """

    def get_extra_art(self, v):
        """ Get additional artwork types from artwork list
        Fanart with language is treated as landscape because it will have text
        """
        artwork = {}

        landscape = [i for i in v.get('backdrops', []) if i.get('iso_639_1') and i.get('aspect_ratio') == 1.778]
        if landscape:
            landscape = sorted(landscape, key=lambda i: i.get('vote_average', 0), reverse=True)
            artwork['landscape'] = self.tmdb_imagepath.get_imagepath_thumbs(landscape[0].get('file_path'))

        clearlogo = [i for i in v.get('logos', []) if i.get('file_path', '')[-4:] != '.svg']
        if clearlogo:
            clearlogo = sorted(clearlogo, key=lambda i: i.get('vote_average', 0), reverse=True)
            artwork['clearlogo'] = self.tmdb_imagepath.get_imagepath_clogos(clearlogo[0].get('file_path'))

        fanart = [i for i in v.get('backdrops', []) if not i.get('iso_639_1') and i.get('aspect_ratio') == 1.778]
        if fanart:
            fanart = sorted(fanart, key=lambda i: i.get('vote_average', 0), reverse=True)
            artwork['fanart'] = self.tmdb_imagepath.get_imagepath_fanart(fanart[0].get('file_path'))

        return artwork

    """
    EPISODE AIRING
    """

    def get_episode_to_air(self, v, name):
        from tmdbhelper.lib.addon.tmdate import format_date_obj, convert_timestamp, get_days_to_air
        i = v or {}
        air_date = i.get('air_date')
        air_date_obj = convert_timestamp(air_date, time_fmt="%Y-%m-%d", time_lim=10, utc_convert=False)
        infoproperties = {}
        infoproperties[f'{name}'] = format_date_obj(air_date_obj, region_fmt='dateshort')
        infoproperties[f'{name}.long'] = format_date_obj(air_date_obj, region_fmt='datelong')
        infoproperties[f'{name}.short'] = format_date_obj(air_date_obj, "%d %b")
        infoproperties[f'{name}.day'] = format_date_obj(air_date_obj, "%A")
        infoproperties[f'{name}.day_short'] = format_date_obj(air_date_obj, "%a")
        infoproperties[f'{name}.year'] = format_date_obj(air_date_obj, "%Y")
        infoproperties[f'{name}.episode'] = i.get('episode_number')
        infoproperties[f'{name}.name'] = i.get('name')
        infoproperties[f'{name}.tmdb_id'] = i.get('id')
        infoproperties[f'{name}.plot'] = i.get('overview')
        infoproperties[f'{name}.season'] = i.get('season_number')
        infoproperties[f'{name}.rating'] = f'{try_float(i.get("vote_average")):0,.1f}'
        infoproperties[f'{name}.votes'] = i.get('vote_count')
        infoproperties[f'{name}.thumb'] = self.tmdb_imagepath.get_imagepath_thumbs(i.get('still_path'))
        infoproperties[f'{name}.original'] = air_date

        if air_date_obj:
            days_to_air, is_aired = get_days_to_air(air_date_obj)
            infoproperties[f'{name}.days_from_aired' if is_aired else f'{name}.days_until_aired'] = str(days_to_air)

        return infoproperties

    """
    CAST
    """

    @staticmethod
    def get_cast_item(i, cast_dict):
        name = i.get('name')
        role = i.get('character') or i.get('role')
        if name not in cast_dict:
            return {'name': name, 'role': role, 'order': i.get('order', 9999)}
        item = cast_dict[name]
        if role and item.get('role') and role not in item['role']:
            item['role'] = f'{item["role"]} / {role}'
        item['order'] = min(item.get('order', 9999), i.get('order', 9999))
        return item

    def get_cast_thumb(self, i):
        if i.get('thumbnail'):
            return i['thumbnail']
        if i.get('profile_path'):
            return self.tmdb_imagepath.get_imagepath_poster(i['profile_path'])

    def get_cast_dict(self, item, base_item=None):
        cast_list = []
        cast_dict = {}
        if base_item and base_item.get('cast'):
            cast_list += base_item['cast']
        if item.get('credits', {}).get('cast'):
            cast_list += item['credits']['cast']
        if item.get('guest_stars'):
            cast_list += item['guest_stars']
        if not cast_list:
            return cast_dict

        # Build a dictionary of cast members to avoid duplicates by combining roles
        for i in cast_list:
            name = i.get('name')
            cast_dict[name] = self.get_cast_item(i, cast_dict)
            if not cast_dict[name].get('thumbnail'):
                cast_dict[name]['thumbnail'] = self.get_cast_thumb(i)

        return cast_dict

    """
    CREW
    """

    def set_crew_properties(self, i, x, prefix):
        infoproperties = {}
        p = f'{prefix}.{x}.'
        if i.get('name'):
            infoproperties[f'{p}name'] = i['name']
        if i.get('job'):
            infoproperties[f'{p}role'] = infoproperties[f'{p}job'] = i['job']
        if i.get('character'):
            infoproperties[f'{p}role'] = infoproperties[f'{p}character'] = i['character']
        if i.get('department'):
            infoproperties[f'{p}department'] = i['department']
        if i.get('profile_path'):
            infoproperties[f'{p}thumb'] = self.tmdb_imagepath.get_imagepath_poster(i['profile_path'])
        if i.get('id'):
            infoproperties[f'{p}tmdb_id'] = i['id']
        return infoproperties

    def get_crew_properties(self, v):
        infoproperties = {}
        department_map = {
            u'Directing': {'name': 'director', 'x': 0},
            u'Writing': {'name': 'writer', 'x': 0},
            u'Production': {'name': 'producer', 'x': 0},
            u'Sound': {'name': 'sound_department', 'x': 0},
            u'Art': {'name': 'art_department', 'x': 0},
            u'Camera': {'name': 'photography', 'x': 0},
            u'Editing': {'name': 'editor', 'x': 0}}
        x = 0
        for i in v:
            if not i.get('name'):
                continue
            x += 1
            if x <= ITER_PROPS_MAX:
                infoproperties.update(self.set_crew_properties(i, x, 'Crew'))
            if i.get('department') not in department_map:
                continue
            dm = department_map[i['department']]
            dm['x'] += 1
            if dm['x'] <= ITER_PROPS_MAX:
                infoproperties.update(self.set_crew_properties(i, dm['x'], dm['name']))
        return infoproperties


class ItemMapper(_ItemMapper, ItemMapperMethods):
    def __init__(self, language=None, mpaa_prefix=None, genres=None):
        self.language = language or get_language()
        self.mpaa_prefix = mpaa_prefix or get_mpaa_prefix()
        self.iso_language = language[:2]
        self.iso_country = language[-2:]
        self.genres = genres or {}
        self.imagepath_quality = 'IMAGEPATH_ORIGINAL'
        self.provider_allowlist = get_setting('provider_allowlist', 'str')
        self.provider_allowlist = self.provider_allowlist.split(' | ') if self.provider_allowlist else []
        self.blacklist = []
        """ Mapping dictionary
        keys:       list of tuples containing parent and child key to add value. [('parent', 'child')]
                    parent keys: art, unique_ids, infolabels, infoproperties, params
                    use UPDATE_BASEKEY for child key to update parent with a dict
        func:       function to call to manipulate values (omit to skip and pass value directly)
        (kw)args:   list/dict of args/kwargs to pass to func.
                    func is also always passed v as first argument
        type:       int, float, str - convert v to type using try_type(v, type)
        extend:     set True to add to existing list - leave blank to overwrite exiting list
        subkeys:    list of sub keys to get for v - i.e. v.get(subkeys[0], {}).get(subkeys[1]) etc.
                    note that getting subkeys sticks for entire loop so do other ops on base first if needed

        use standard_map for direct one-to-one mapping of v onto single property tuple
        """
        self.advanced_map = {
            'episodes': [{
                'keys': [('infolabels', 'episode')],
                'func': lambda v: f'{len(v)}'
            }],
            'poster_path': [{
                'keys': [('art', 'poster')],
                'func': self.tmdb_imagepath.get_imagepath_poster
            }],
            'profile_path': [{
                'keys': [('art', 'poster'), ('art', 'profile')],
                'func': self.tmdb_imagepath.get_imagepath_poster
            }],
            'file_path': [{
                'keys': [('art', 'poster'), ('art', 'file')],
                'func': self.tmdb_imagepath.get_imagepath_origin
            }],
            'still_path': [{
                'keys': [('art', 'thumb'), ('art', 'still')],
                'func': self.tmdb_imagepath.get_imagepath_thumbs
            }],
            'logo_path': [{
                'keys': [('art', 'thumb'), ('art', 'logo')],
                'func': self.tmdb_imagepath.get_imagepath_origin
            }],
            'backdrop_path': [{
                'keys': [('art', 'fanart'), ('art', 'backdrop')],
                'func': self.tmdb_imagepath.get_imagepath_fanart
            }],
            'content_ratings': [{
                'keys': [('infolabels', 'mpaa')],
                'subkeys': ['results'],
                'func': self.get_mpaa_rating,
                'args': [self.mpaa_prefix, self.iso_country, False]
            }],
            'release_dates': [{
                'keys': [('infolabels', 'mpaa')],
                'subkeys': ['results'],
                'func': self.get_mpaa_rating,
                'args': [self.mpaa_prefix, self.iso_country, True]}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['results'],
                'func': self.get_release_types,
                'args': [self.iso_country]
            }],
            'release_date': [{
                'keys': [('infolabels', 'premiered')]}, {
                'keys': [('infolabels', 'year')],
                'func': lambda v: int(v[0:4])
            }],
            'first_air_date': [{
                'keys': [('infolabels', 'premiered')]}, {
                'keys': [('infolabels', 'year')],
                'func': lambda v: int(v[0:4])
            }],
            'air_date': [{
                'keys': [('infolabels', 'premiered')]}, {
                'keys': [('infolabels', 'year')],
                'func': lambda v: int(v[0:4])
            }],
            'genre_ids': [{
                'keys': [('infolabels', 'genre')],
                'func': self.get_genres_by_id
            }],
            'videos': [{
                'keys': [('infolabels', 'trailer')],
                'func': self.get_trailer,
                'args': [self.iso_language]
            }],
            'popularity': [{
                'keys': [('infoproperties', 'popularity')],
                'type': str
            }],
            'vote_count': [{
                'keys': [('infolabels', 'votes')],
                'type': int}, {
                'keys': [('infoproperties', 'tmdb_votes')],
                'type': float,
                'func': lambda v: f'{v:0,.0f}'
            }],
            'vote_average': [{
                'keys': [('infolabels', 'rating')],
                'type': float}, {
                'keys': [('infoproperties', 'tmdb_rating')],
                'type': float,
                'func': lambda v: f'{v:.1f}'
            }],
            'budget': [{
                'keys': [('infoproperties', 'budget')],
                'type': float,
                'func': lambda v: f'${v:0,.0f}'
            }],
            'revenue': [{
                'keys': [('infoproperties', 'revenue')],
                'type': float,
                'func': lambda v: f'${v:0,.0f}'
            }],
            'spoken_languages': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.iter_props,
                'args': ['language'],
                'kwargs': {'name': 'name', 'iso': 'iso_639_1'}
            }],
            'keywords': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['keywords'],
                'func': self.iter_props,
                'args': ['keyword'],
                'kwargs': {'name': 'name', 'tmdb_id': 'id'}
            }],
            'reviews': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['results'],
                'func': self.iter_props,
                'args': ['review'],
                'kwargs': {'content': 'content', 'author': 'author', 'tmdb_id': 'id'}
            }],
            'created_by': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_iter_props,
                'args': ['creator'],
                'kwargs': {
                    'basic_keys': {'name': 'name', 'tmdb_id': 'id'},
                    'image_keys': {'thumb': 'profile_path'}}}, {
                # ---
                'keys': [('infoproperties', 'creator')],
                'func': lambda v: ' / '.join([x['name'] for x in v or [] if x.get('name')])
            }],
            'also_known_as': [{
                'keys': [('infoproperties', 'aliases')],
                'func': lambda v: ' / '.join([x for x in v or [] if x])
            }],
            'known_for': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.iter_props,
                'args': ['known_for'],
                'kwargs': {'title': 'title', 'tmdb_id': 'id', 'rating': 'vote_average', 'tmdb_type': 'media_type'}}, {
                # ---
                'keys': [('infoproperties', 'known_for')],
                'func': lambda v: ' / '.join([x['title'] for x in v or [] if x.get('title')])
            }],
            'roles': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_roles,
                'kwargs': {'key': 'character'}
            }],
            'jobs': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_roles,
                'kwargs': {'key': 'job'}
            }],
            'external_ids': [{
                'keys': [('unique_ids', UPDATE_BASEKEY)],
                'func': self.get_external_ids
            }],
            'images': [{
                'keys': [('art', UPDATE_BASEKEY)],
                'func': self.get_extra_art
            }],
            'credits': [{
                'keys': [('infolabels', UPDATE_BASEKEY)],
                'func': self.get_credits}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['crew'],
                'func': self.get_crew_properties
            }],
            'parts': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_collection_properties
            }],
            'movie_credits': [{
                'keys': [('infoproperties', 'numitems.tmdb.movies.cast')],
                'func': lambda v: len(v.get('cast') or [])}, {
                # ---
                'keys': [('infoproperties', 'numitems.tmdb.movies.crew')],
                'func': lambda v: len(v.get('crew') or [])}, {
                # ---
                'keys': [('infoproperties', 'numitems.tmdb.movies.total')],
                'func': lambda v: len(v.get('cast') or []) + len(v.get('crew') or [])}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['cast'],
                'func': self.get_iter_props,
                'args': ['movie.cast'],
                'kwargs': {
                    'sorted': {'key': lambda i: i.get('popularity', 0), 'reverse': True},
                    'basic_keys': {'title': 'title', 'tmdb_id': 'id', 'plot': 'overview', 'rating': 'vote_average', 'votes': 'vote_count', 'character': 'character', 'premiered': 'release_date'},
                    'image_keys': {'poster': 'poster_path'},
                    'fanart_keys': {'fanart': 'backdrop_path'}}}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['crew'],
                'func': self.get_iter_props,
                'args': ['movie.crew'],
                'kwargs': {
                    'sorted': {'key': lambda i: i.get('popularity', 0), 'reverse': True},
                    'basic_keys': {'title': 'title', 'tmdb_id': 'id', 'plot': 'overview', 'rating': 'vote_average', 'votes': 'vote_count', 'department': 'department', 'job': 'job', 'premiered': 'release_date'},
                    'image_keys': {'poster': 'poster_path'},
                    'fanart_keys': {'fanart': 'backdrop_path'}}
            }],
            'tv_credits': [{
                'keys': [('infoproperties', 'numitems.tmdb.tvshows.cast')],
                'func': lambda v: len(v.get('cast') or [])}, {
                # ---
                'keys': [('infoproperties', 'numitems.tmdb.tvshows.crew')],
                'func': lambda v: len(v.get('crew') or [])}, {
                # ---
                'keys': [('infoproperties', 'numitems.tmdb.tvshows.total')],
                'func': lambda v: len(v.get('cast') or []) + len(v.get('crew') or [])}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['cast'],
                'func': self.get_iter_props,
                'args': ['tvshow.cast'],
                'kwargs': {
                    'sorted': {'key': lambda i: i.get('popularity', 0), 'reverse': True},
                    'basic_keys': {'title': 'name', 'tmdb_id': 'id', 'plot': 'overview', 'rating': 'vote_average', 'votes': 'vote_count', 'character': 'character', 'premiered': 'first_air_date', 'episodes': 'episode_count'},
                    'image_keys': {'poster': 'poster_path'},
                    'fanart_keys': {'fanart': 'backdrop_path'}}}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['crew'],
                'func': self.get_iter_props,
                'args': ['tvshow.crew'],
                'kwargs': {
                    'sorted': {'key': lambda i: i.get('popularity', 0), 'reverse': True},
                    'basic_keys': {'title': 'name', 'tmdb_id': 'id', 'plot': 'overview', 'rating': 'vote_average', 'votes': 'vote_count', 'department': 'department', 'job': 'job', 'premiered': 'first_air_date', 'episodes': 'episode_count'},
                    'image_keys': {'poster': 'poster_path'},
                    'fanart_keys': {'fanart': 'backdrop_path'}}
            }],
            'belongs_to_collection': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_collection}, {
                # ---
                'keys': [('infolabels', 'set')],
                'subkeys': ['name']
            }],
            'episode_run_time': [{
                'keys': [('infolabels', 'duration')],
                'func': self.get_runtime
            }],
            'runtime': [{
                'keys': [('infolabels', 'duration')],
                'func': self.get_runtime
            }],
            'genres': [{
                'keys': [('infolabels', 'genre')],
                'func': dict_to_list,
                'args': ['name']}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.iter_props,
                'args': ['genre'],
                'kwargs': {'name': 'name', 'tmdb_id': 'id'}
            }],
            'production_countries': [{
                'keys': [('infolabels', 'country')],
                'extend': True,
                'func': dict_to_list,
                'args': ['name']}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.iter_props,
                'args': ['country'],
                'kwargs': {'name': 'name', 'tmdb_id': 'id'}
            }],
            'networks': [{
                'keys': [('infolabels', 'studio')],
                'extend': True,
                'func': dict_to_list,
                'args': ['name']}, {
                # ---
                'keys': [('infoproperties', 'network')],
                'func': lambda v: ' / '.join([x['name'] for x in v or [] if x.get('name')])}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_iter_props,
                'args': ['network'],
                'kwargs': {
                    'basic_keys': {'name': 'name', 'tmdb_id': 'id'},
                    'image_keys': {'icon': 'logo_path'},
                    'negativeimage_keys': {'monoicon': 'logo_path'}}
            }],
            'production_companies': [{
                'keys': [('infolabels', 'studio')],
                'extend': True,
                'func': dict_to_list,
                'args': ['name']}, {
                # ---
                'keys': [('infoproperties', 'studio')],
                'func': lambda v: v[0].get('name') if v else ''}, {
                # ---
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_iter_props,
                'args': ['studio'],
                'kwargs': {
                    'basic_keys': {'name': 'name', 'tmdb_id': 'id'},
                    'image_keys': {'icon': 'logo_path'},
                    'negativeimage_keys': {'monoicon': 'logo_path'}}
            }],
            'watch/providers': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'subkeys': ['results', self.iso_country],
                'kwargs': {'allowlist': self.provider_allowlist},
                'func': self.get_providers
            }],
            'last_episode_to_air': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_episode_to_air,
                'args': ['last_aired']
            }],
            'next_episode_to_air': [{
                'keys': [('infoproperties', UPDATE_BASEKEY)],
                'func': self.get_episode_to_air,
                'args': ['next_aired']
            }],
            'imdb_id': [{
                'keys': [('infolabels', 'imdbnumber'), ('unique_ids', 'imdb')]
            }],
            'episode_count': [{
                'keys': [('infolabels', 'episode'), ('infoproperties', 'episodes')]
            }],
            'group_count': [{
                'keys': [('infolabels', 'season'), ('infoproperties', 'seasons')]
            }],
            'character': [{
                'keys': [('infoproperties', 'role'), ('infoproperties', 'character'), ('label2', None)]
            }],
            'job': [{
                'keys': [('infoproperties', 'role'), ('infoproperties', 'job'), ('label2', None)]
            }],
            'biography': [{
                'keys': [('infoproperties', 'biography'), ('infolabels', 'plot')]
            }],
            'gender': [{
                'keys': [('infoproperties', 'gender')],
                'func': lambda v, d: d.get(v),
                'args': [{
                    1: get_localized(32071),
                    2: get_localized(32070)}]
            }]
        }
        self.standard_map = {
            'overview': ('infolabels', 'plot'),
            'content': ('infolabels', 'plot'),
            'tagline': ('infolabels', 'tagline'),
            'id': ('unique_ids', 'tmdb'),
            'provider_id': ('unique_ids', 'tmdb'),
            'original_title': ('infolabels', 'originaltitle'),
            'original_name': ('infolabels', 'originaltitle'),
            'title': ('infolabels', 'title'),
            'name': ('infolabels', 'title'),
            'author': ('infolabels', 'title'),
            'provider_name': ('infolabels', 'title'),
            'origin_country': ('infolabels', 'country'),
            'status': ('infolabels', 'status'),
            'season_number': ('infolabels', 'season'),
            'episode_number': ('infolabels', 'episode'),
            'season_count': ('infolabels', 'season'),
            'number_of_seasons': ('infolabels', 'season'),
            'number_of_episodes': ('infolabels', 'episode'),
            'department': ('infoproperties', 'department'),
            'known_for_department': ('infoproperties', 'department'),
            'place_of_birth': ('infoproperties', 'born'),
            'birthday': ('infoproperties', 'birthday'),
            'deathday': ('infoproperties', 'deathday'),
            'width': ('infoproperties', 'width'),
            'height': ('infoproperties', 'height'),
            'aspect_ratio': ('infoproperties', 'aspect_ratio'),
            'original_language': ('infoproperties', 'original_language')
        }

    def get_genres_by_id(self, v):
        genre_ids = v or []
        genre_map = {v: k for k, v in self.genres.items()}
        return [i for i in (genre_map.get(try_int(genre_id)) for genre_id in genre_ids) if i]

    def finalise(self, item, tmdb_type):

        def finalise_image():
            item['infolabels']['title'] = f'{item["infoproperties"].get("width")}x{item["infoproperties"].get("height")}'
            item['params'] = -1
            item['path'] = item['art'].get('thumb') or item['art'].get('poster') or item['art'].get('fanart')
            item['is_folder'] = False
            item['library'] = 'pictures'

        def finalise_person():
            from tmdbhelper.lib.addon.tmdate import age_difference
            if item['infoproperties'].get('birthday'):
                item['infoproperties']['age'] = age_difference(
                    item['infoproperties']['birthday'],
                    item['infoproperties'].get('deathday'))

        def finalise_tv():
            item['infolabels']['tvshowtitle'] = item['infolabels'].get('title')

        def finalise_video():
            item['params'] = -1

        finalise_route = {
            'image': finalise_image,
            'person': finalise_person,
            'tv': finalise_tv,
            'video': finalise_video}

        if tmdb_type in finalise_route:
            finalise_route[tmdb_type]()

        item['label'] = item['infolabels'].get('title')
        item['infoproperties']['tmdb_type'] = tmdb_type
        item['infolabels']['mediatype'] = item['infoproperties']['dbtype'] = convert_type(tmdb_type, 'dbtype')
        for k, v in item['unique_ids'].items():
            item['infoproperties'][f'{k}_id'] = v

        return item

    def add_cast(self, item, info_item, base_item=None):
        cast_dict = self.get_cast_dict(info_item, base_item)
        if not cast_dict:
            return item
        cast_list, cast_prop = [], []
        for x, i in enumerate(sorted(cast_dict, key=lambda k: cast_dict[k].get('order', 9999)), start=1):
            i = cast_dict[i]
            if not i or not i['name']:
                continue
            if x <= ITER_PROPS_MAX:
                p = f'Cast.{x}.'
                for j in [('name', 'Name'), ('role', 'Role'), ('thumbnail', 'Thumb')]:
                    item['infoproperties'][f'{p}{j[1]}'] = i.get(j[0], '')
            cast_prop.append(i['name'])
            cast_list.append(i)
        item['infoproperties']['cast'] = " / ".join(cast_prop)
        item['cast'] = cast_list
        return item

    def add_infoproperties(self, item, infoproperties):
        if not infoproperties:
            return item
        for k, v in infoproperties:
            item['infoproperties'][k] = v
        return item

    def get_info(self, info_item, tmdb_type, base_item=None, base_is_season=False, add_infoproperties=None, **kwargs):
        item = get_empty_item()
        item = self.map_item(item, info_item)
        item = self.add_base(item, base_item, tmdb_type, key_blacklist=['year', 'premiered', 'season', 'episode'], is_season=base_is_season)
        item = self.add_cast(item, info_item, base_item)
        item = self.add_infoproperties(item, add_infoproperties)
        item = self.finalise(item, tmdb_type)
        item['params'] = get_params(info_item, tmdb_type, params=item.get('params', {}), **kwargs)
        return item
