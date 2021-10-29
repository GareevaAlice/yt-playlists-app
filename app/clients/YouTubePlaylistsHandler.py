from urllib.parse import urlencode
import requests
import pandas as pd
from typing import Dict
import googleapiclient.discovery
import google.oauth2.credentials
from flask import session
import os


# -----------------------------------------------------------
# Данный класс позволяет получать основную информацию о каждом видео
# из неприватного плейлиста YouTube в формате pd.DataFrame:
# номер видео в плейлисте, ссылку на видео, ссылку на изображение превью видео,
# название видео, описание видео, ник автора видео.
# Класс использует один API сервис:
# YouTube Data API v3
# (https://developers.google.com/youtube/v3/getting-started)
# для работы с PlaylistItems - получение информации о видео из плейлиста
# (https://developers.google.com/youtube/v3/docs/playlistItems)
# и для работы с Playlists - проверка доступности плейлиста
# (https://developers.google.com/youtube/v3/docs/playlists)
# (Бесплатное использование c ограничениями 10,000 запросов в день.
# Доступ по api-key.)
# -----------------------------------------------------------

class YouTubePlaylistsHandler:
    """ Класс получения основной информации о плейлисте. """

    class CannotGetError(Exception):
        """ Класс исключения, информирующий о том,
            что невозможно получить информацию о плейлисте. """
        message = \
            'Нельзя получить информацию о данном плейлисте:' \
            ' он не существует или имеет приватные настройки доступа.' \
            ' <br>' \
            'Также проверьте правильность youtube-api-key.'

    class UndefinedError(Exception):
        """ Класс исключения, информирующий о том,
            что невозможно связаться с API. """
        message = \
            'Не можем связаться с API для работы с youtube: ' \
            ' <br>' \
            ' проверьте свой api-key,' \
            ' попробуйте повторить свои действия или подождать.'

    @staticmethod
    def get_playlist_id(playlist_url_or_id: str) -> str:
        """
        Функция получения id плейлиста по ссылке.

        :param playlist_url_or_id: ссылка или id плейлиста
        :return: id плейлиста
        """
        playlist_id = playlist_url_or_id
        if 'youtube' in playlist_url_or_id:
            playlist_id = playlist_url_or_id.split('=')[-1]
        return playlist_id

    def __init__(self, youtube_api_key: str, client_secret=None):
        """
        :param youtube_api_key: api-key для доступа к YouTube Data API v3
        :param client_secret: путь к файлу, где лежит client_secret для OAuth
        """
        self.youtube_api_key = youtube_api_key
        self.client_secret = client_secret
        self.df_searcher = None  # класс для поиска по плейлисту
        self.work_playlist_id = None  # id плейлиста с которым работает класс

    @staticmethod
    def yt_api_key_from_file(api_key_file_path: str, client_secret=None) \
            -> 'YouTubePlaylistsHandler':
        """
        Функция инициализации класса через путь к файлу, где лежит api-key.

        :param api_key_file_path: путь к файлу, где лежит api-key
        :param client_secret: путь к файлу, где лежит client_secret для OAuth
        :return: YouTubePlaylistsHandler
        """
        with open(api_key_file_path) as f:
            youtube_api_key = f.read()
        if client_secret is not None and not os.path.exists(client_secret):
            client_secret = None
        return YouTubePlaylistsHandler(youtube_api_key=youtube_api_key,
                                       client_secret=client_secret)

    def __call__(self, playlist_url_or_id: str, oauth=False) -> pd.DataFrame:
        """
        Основная функция получения информации о видео в плейлисте.

        :param playlist_url_or_id:  ссылка или id плейлиста
        :param oauth: авторизирован ли пользователь (default False)
        :return: pd.DataFrame с основной информацией,
            о каждом видео из плейлиста:
            'ind' - номера видео в плейлисте
            'url' - ссылки на видео
            'img_url' - ссылки на изображения превью видео
            'title' - названия видео
            'description' - описания видео
            'author_url' - ссылки на авторов видео
            'author' - ники авторов видео
        """
        # получение id плейлиста
        playlist_id = self.get_playlist_id(playlist_url_or_id)
        if oauth:
            # пользователь авторизован
            data_frame = self._oauth_get_all_data_frame(playlist_id)
        else:
            # пользователь не авторизован
            self._check_playlist(playlist_id)  # проверка доступности плейлиста
            data_frame = self._get_all_data_frame(playlist_id)
        # обновляем id плейлиста, с которым работает класс
        self.work_playlist_id = playlist_id
        # таблица pd.DataFrame с информации о видео в плейлисте
        return data_frame

    def _check_playlist(self, playlist_id: str) -> None:
        """
        Проверка доступности плейлиста с помощью Playlists.

        :param playlist_id: id плейлиста
        :return вызывает ошибку, если плейлист недоступен
        """
        url = 'https://www.googleapis.com/youtube/v3/playlists'
        params = {
            'id': playlist_id,
            'part': 'status',
            'key': self.youtube_api_key
        }
        req_url = url + '?' + urlencode(params)  # делаем ссылку
        response = requests.get(req_url)
        # невозможно получить доступ
        if response.status_code != 200 \
                or response.json()['pageInfo']['totalResults'] == 0:
            raise self.CannotGetError

    def _get_all_data_frame(self, playlist_id: str) -> pd.DataFrame:
        """
        Функция получения основной информации
            о каждом видео из плейлиста в формате pd.DataFrame.

        :param playlist_id: id плейлиста
        :return: pd.DataFrame с основной информацией,
            о каждом видео из плейлиста
        """
        status_ok = True
        # создаем словарь информации
        info = self._create_info()
        # получение первой страницы
        response = self._get_page_response(playlist_id)
        # сбор информации с первой страницы
        status_ok &= self._get_info(info, response)

        # проход по всем страницами плейлиста
        while 'nextPageToken' in response.json():
            # получение номера следующей страницы
            page_token = response.json()['nextPageToken']
            response = self._get_page_response(playlist_id, page_token)
            status_ok &= self._get_info(info, response)

        if not status_ok:  # что-то пошло не так
            raise self.UndefinedError
        # получаем таблицу pd.DataFrame
        return self._info_to_data_frame(info)

    def _get_page_response(self, playlist_id: str,
                           page_token=None) -> 'Response':
        """
        Функция получения ответа от PlaylistItems
            - информация о 50 видео на n "странице" плейлиста.
        (API позволяет получить максимально 50 видео,
            храня все в связном списке из страниц)

        :param playlist_id: id плейлиста
        :param page_token: "номер" страницы (default None - первая страница)
        :return: Response от playlistItems с информацией о 50 видео
        """
        url = 'https://www.googleapis.com/youtube/v3/playlistItems'
        params = {
            'playlistId': playlist_id,
            'part': 'snippet, status',
            'maxResults': 50,
            'key': self.youtube_api_key
        }
        if page_token is not None:
            params['pageToken'] = page_token

        req_url = url + '?' + urlencode(params)  # делаем ссылку
        return requests.get(req_url)

    @staticmethod
    def _create_info() -> Dict:
        """
        Функция создания словаря,
            где будут храниться списки информации о каждом видео.

        :return: словарь с информацией о каждом видео
        """
        return {
            'curr': 0,  # текущий номер в плейлисте
            'indexes': [],  # номера видео в плейлисте
            'urls': [],  # ссылки на видео
            'img_urls': [],  # ссылки на изображения превью видео
            'titles': [],  # названия видео
            'descriptions': [],  # описания видео
            'author_urls': [],  # ссылка на автора видео
            'authors': []  # ники авторов видео
        }

    def _get_info(self, info, response) -> bool:
        """
        Функция получения основной информации,
            о каждом видео из ответа PlaylistItems.

        :param info: словарь, где хранятся списки информации о каждом видео
        :param response: ответ от PlaylistItems
        :return: прошло ли все хорошо или произошла ошибка
        """
        if response.status_code != 200:  # невозможно получить ответ
            return False
        items = response.json()['items']
        for i in range(len(items)):
            # текущий номер в плейлисте
            info['curr'] += 1
            status = items[i]['status']['privacyStatus']
            # видео удалено или имеет приватные настройки доступа
            if status != 'public' and status != 'unlisted':
                continue
            # номер видео в плейлисте
            info['indexes'].append(info['curr'])
            # подробная информация об одном видео
            item = items[i]['snippet']
            # зполнение словаря с информацией
            self._fill_info(info, item)
        return True

    @staticmethod
    def _fill_info(info: Dict, item: Dict) -> None:
        """
        Функция заполнения подробной информации от одного видео.

        :param info: словарь, где хранятся списки информации о каждом видео
        :param item: подробная информация
            об одном видео из ответа PlaylistItems
        """
        video_id = item['resourceId']['videoId']
        # ссылка на видео
        video_url = f'https://www.youtube.com/watch?v={video_id}'
        info['urls'].append(video_url)
        # ссылка на изображение превью видео
        video_img_url = f'https://img.youtube.com/vi/{video_id}/0.jpg'
        info['img_urls'].append(video_img_url)
        # название видео
        info['titles'].append(item['title'])
        # описание видео
        info['descriptions'].append(item['description'])
        # ссылка на автора видео
        author_id = item['videoOwnerChannelId']
        author_url = f'https://www.youtube.com/channel/{author_id}'
        info['author_urls'].append(author_url)
        # ник автора видео
        info['authors'].append(item['videoOwnerChannelTitle'])

    @staticmethod
    def _info_to_data_frame(info: Dict):
        """
        Функция создания pd.DataFrame с основной информацией
            о каждом видео из плейлиста на снове словаря info
        :param info: словарь, где хранятся списки информации о каждом видео
        :return: pd.DataFrame
        """
        return pd.DataFrame(
            {
                # номера видео в плейлисте
                'ind': info['indexes'],
                # ссылки на видео
                'url': info['urls'],
                # ссылки на изображения превью видео
                'img_url': info['img_urls'],
                # названия видео
                'title': info['titles'],
                # описания видео
                'description': info['descriptions'],
                # ссылки на авторов видео
                'author_url': info['author_urls'],
                # ники авторов видео
                'author': info['authors']
            }
        )

    # -----------------------------------------------------------
    # Функции и классы для работы с OAuth.
    # (https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps)
    # Для работы надо провести настройку в консоле API.
    # Подробнее написано в README.md.
    # -----------------------------------------------------------

    class OAuthUndefinedError(Exception):
        """ Класс исключения, информирующий о том,
                    что невозможно связаться с OAuth или API. """
        message = \
            ' Что-то пошло не так:' \
            ' проверьте, что Вы правильно настроили OAuth' \
            ' и имеете доступ к плейлисту.'

    def _oauth_get_all_data_frame(self, playlist_id: str) -> pd.DataFrame:
        """
        Функция - аналог функции _get_all_data_frame, но для работы с OAuth.
        Функция получения основной информации
            о каждом видео из плейлиста в формате pd.DataFrame.

        :param playlist_id: id плейлиста
        :return: pd.DataFrame с основной информацией,
            о каждом видео из плейлиста
        """
        # Загружаем учетные данные из сеанса.
        credentials = \
            google.oauth2.credentials.Credentials(**session['credentials'])
        # Класс для работы с запросами.
        self.youtube = googleapiclient.discovery.build(
            'youtube',
            'v3',
            credentials=credentials)
        try:
            # создаем словарь информации
            info = self._create_info()
            # получение первой страницы для авторизованного пользователя
            response = self._oauth_get_page_response(playlist_id)
            # сбор информации с первой страницы
            # для авторизованного пользователя
            self._oauth_get_info(info, response)

            # проход по всем страницами плейлиста
            while 'nextPageToken' in response.execute():
                # получение номера следующей страницы
                page_token = response.execute()['nextPageToken']
                response = self._oauth_get_page_response(playlist_id,
                                                         page_token)
                self._oauth_get_info(info, response)
        # что-то пошло не так
        except googleapiclient.errors.HttpError:
            raise self.OAuthUndefinedError
        # получаем таблицу pd.DataFrame
        return self._info_to_data_frame(info)

    def _oauth_get_page_response(self, playlist_id: str,
                                 page_token=None) -> 'HttpRequest':
        """
        Функция - аналог функции _get_page_response, но для работы с OAuth.
        Функция получения ответа от PlaylistItems
            - информация о 50 видео на n "странице" плейлиста.
        (API позволяет получить максимально 50 видео,
            храня все в связном списке из страниц)

        :param playlist_id: id плейлиста
        :param page_token: "номер" страницы (default None - первая страница)
        :return: HttpRequest от playlistItems с информацией о 50 видео
        """
        if page_token is not None:
            response = self.youtube.playlistItems().list(
                playlistId=playlist_id,
                part="snippet",
                maxResults=50,
                pageToken=page_token
            )
        else:
            response = self.youtube.playlistItems().list(
                playlistId=playlist_id,
                part="snippet",
                maxResults=50
            )
        return response

    def _oauth_get_info(self, info: Dict, response: 'HttpRequest') -> None:
        """
        Функция - аналог функции _get_info, но для работы с OAuth.
        Функция получения основной информации,
            о каждом видео из ответа PlaylistItems.

        :param info: словарь, где хранятся списки информации о каждом видео
        :param response: ответ от PlaylistItems в формате HttpRequest
        """
        items = response.execute()['items']
        for i in range(len(items)):
            info['curr'] += 1  # текущий номер в плейлисте
            # видео не принадлежит пользователю и имеет приватный доступа
            if 'videoOwnerChannelId' not in items[i]['snippet']:
                continue
            # номер видео в плейлисте
            info['indexes'].append(info['curr'])
            # подробная информация об одном видео
            item = items[i]['snippet']
            # зполнение словаря с информацией
            self._fill_info(info, item)
