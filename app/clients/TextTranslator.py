from urllib.parse import urlencode
import requests


# -----------------------------------------------------------
# Данный класс позволяет переводить текст с русского на английский
# и с английского на русский
# без дополнительной информации о том,
# какой конкретно перевод нужно выполнить.
# Класс использует два API сервиса:
# > Detect Language API - для определения языка текста
# (https://detectlanguage.com)
# (Бесплатное использование c ограничениями 1000 слов в день.
# Доступ по api-key.)
# > MyMemory API - для перевода текста
# (https://mymemory.translated.net/doc/spec.php)
# (Бесплатное анонимное использование c ограничением 1000 слов в день.
# Доступ без api-key.)
# -----------------------------------------------------------

class TextTranslator:
    """ Класс перевода текста
        с русского на английский и с английского на русский. """

    class UndefinedError(Exception):
        """ Класс исключения, информирующий о том,
            что невозможно связаться с API. """
        message = \
            'Не можем связаться с API для работы с языками:' \
            ' <br>' \
            ' проверьте свой detectlanguage-api-key,' \
            ' попробуйте повторить свои действия или подождать.'

    class NothingError(Exception):
        """ Класс исключения, информирующий о том,
            что невозможно сделать перевод. """
        message = \
            'Невозможно сделать перевод для данного текста.'

    def __init__(self, detect_language_api_key: str):
        """
        :param detect_language_api_key: api-key
            для доступа к Detect Language API
        """
        self.detect_language_api_key = detect_language_api_key

    @staticmethod
    def dl_api_key_from_file(api_key_file_path: str) -> 'TextTranslator':
        """
        Функция инициализации класса через путь к файлу, где лежит api-key.

        :param api_key_file_path: путь к файлу, где лежит api-key
        :return: TextTranslator
        """
        with open(api_key_file_path) as f:
            detect_language_api_key = f.read()
        return TextTranslator(detect_language_api_key=detect_language_api_key)

    def __call__(self, text: str) -> str:
        """
        Основная функция перевода текста.

        :param text: текст для перевода
        :return: перевод текста
            с русского на английский и с английского на русский
        """
        # если нет текста - не надо ничего переводить
        if text == '':
            return ''
        language = self._detect_language(text)  # определяем язык
        if language == 'ru':
            languages = 'ru|en'
        elif language == 'en':
            languages = 'en|ru'
        else:
            # введенный текст не написан на русском или английском
            raise self.NothingError
        # переведенный текст на второй язык
        return self._get_translation(text, languages)

    def _detect_language(self, text: str) -> str:
        """
        Функция определения языка, использующая Detect Language API.

        :param text: текст для определения языка
        :return: язык текста
        """
        response = self._get_detect_language_response(text)
        if response.status_code != 200:  # невозможно получить ответ
            raise self.UndefinedError
        # получаем язык текста
        detections = response.json()['data']['detections']
        if len(detections) > 0:
            return detections[0]['language']
        raise self.NothingError  # невозможно определить язык

    def _get_detect_language_response(self, text: str) -> 'Response':
        """
        Функция получения ответа для определения языка от Detect Language API.

        :param text: текст для определения языка
        :return: Response от Detect Language API с определением языка текста
        """
        url = 'https://ws.detectlanguage.com/0.2/detect'
        headers = {'Authorization': 'Bearer ' + self.detect_language_api_key}
        json = {'q': text}
        return requests.post(url, json=json, headers=headers)

    def _get_translation(self, text: str, languages: str) -> str:
        """
        Функция перевода, использующая MyMemory API.

        :param text: текст для перевода
        :param languages: с какого на какой язык
            надо переводить (ru|en или en|ru)
        :return: переведенный текст
        """
        # получение ответа от MyMemory API
        response = self._get_translation_response(text, languages)
        if response.status_code != 200:  # невозможно получить ответ
            raise self.UndefinedError
        # получаем перевод
        matches = response.json()['matches']
        if len(matches) > 0:
            return matches[0]['translation']
        raise self.NothingError  # невозможно сделать перевод

    @staticmethod
    def _get_translation_response(text: str, languages: str) -> 'Response':
        """
        Функция получения ответа для перевода от MyMemory API.

        :param text: текст для перевода
        :param languages: с какого на какой язык
            надо переводить (ru|en или en|ru)
        :return: Response от MyMemory API с переводом текста
        """
        url = 'https://api.mymemory.translated.net/get'
        params = {
            'q': text,
            'langpair': languages
        }
        req_url = url + '?' + urlencode(params)  # делаем ссылку
        return requests.get(req_url)
