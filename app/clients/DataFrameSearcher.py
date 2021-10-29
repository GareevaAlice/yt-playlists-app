from typing import Union, Dict
import pandas as pd

from app.clients.TextTranslator import TextTranslator


# -----------------------------------------------------------
# Данный класс позволяет искать в pd.DataFrame,
# состоящий из информации о каждом из видео в плейлисте,
# по различным критериям:
# по названию / по названию и описанию,
# дословный поиск / поиск слов в любом порядке, по нику автора
# и по двум языкам одновременно (на русском и английском),
# находя соответствие хотя бы в одном из вариантов перевода.
# (Для этого требуется ввести путь до api-key для Detect Language API
# (https://detectlanguage.com))
# -----------------------------------------------------------

class DataFrameSearcher:
    """ Класс поиска плейлистов по pd.DataFrame. """

    class NothingError(Exception):
        """ Класс исключения, информирующий о том,
            что в pd.DataFrame не нашлось нужного плейлиста. """
        message = \
            'По данному запросу ничего не нашлось.'

    def __init__(self,
                 data_frame: Union[pd.DataFrame, None],
                 dl_api_key_file_path: str):
        """
        :param data_frame: таблица с данными о каждом из видео в плейлисте
        ('title' - название, 'description' - описание, 'author' - ник автора)
        :param dl_api_key_file_path: путь к файлу,
            где лежит api-key для доступа к Detect Language API
        """
        self.df = data_frame
        # класс для переводов
        self.text_translator = \
            TextTranslator.dl_api_key_from_file(dl_api_key_file_path)

    def __call__(self,
                 code_words: str,
                 author_name=None,
                 search_by_description=False,
                 verbatim_search=True,
                 bilingual_search=False) -> Dict:
        """
        Основная функция поиска нужных видео по критериям.

        :param code_words: ключевые слова для поиска
        :param author_name: ник автора для поиска (default None)
        :param search_by_description: надо ли искать
            по описанию (default False)
        :param verbatim_search: тип поиска: True - дословный,
            False - в любом порядке (default True)
        :param bilingual_search: надо ли искать
            по двум языкам (default False)
        :return:
            словарь dict(
                'data_frame' : таблица pd.DataFrame только из нужных нам видео,
                'translation' : перевод при двуязычном поиске (иначе - None)
            )
        """
        translation = None
        # перевести ключевые слова при двуязычном поиске
        if bilingual_search:
            translation = self.text_translator(code_words)

        if verbatim_search:
            # дословный поиск
            self.df['found_words'] = self.df.apply(
                lambda video:
                self._verbatim_search(video,
                                      code_words,
                                      search_by_description,
                                      translation),
                axis=1).astype('int')
        else:
            # поиск слов в любом порядке
            self.df['found_words'] = self.df.apply(
                lambda video:
                self._not_verbatim_search(video,
                                          code_words,
                                          search_by_description,
                                          translation),
                axis=1).astype('int')

        # поиск по автору
        self.df['found_author'] = self.df.apply(
            lambda video:
            self._author_search(video, author_name),
            axis=1).astype('int')

        # нахождение нужных видео
        cond = (self.df['found_words'] > 0) & (self.df['found_author'] > 0)
        new_df = self.df[cond]

        # приводим перевод к одному регистру
        if translation is not None:
            translation = translation.lower()
        return {
            # таблица только из нужных нам видео
            'data_frame': new_df,
            # перевод при двуязычном поиске (иначе - None)
            'translation': translation
        }

    @staticmethod
    def _verbatim_search(video,
                         code_words: str,
                         search_by_description: bool,
                         translation=None) -> bool:
        """
        Функция для дословного поиска.
        Определяет подходит ли конкретное видео под заданные условия.

        :param video: строка в data_frame со всей информации о конкретном видео
        :param code_words: ключевые слова для поиска
        :param search_by_description: надо ли искать по описанию
        :param translation: перевод текста,
            если поиск по двум языкам (default None)
        :return: True - видео подходит, False - видео не подходит
        """
        # если нет ключевых слов - подходит любое видео
        if code_words == '':
            return True

        # поиск независимо от регистра
        code_words = code_words.lower()
        text = video['title'].lower()
        # поиск по описанию тоже
        if search_by_description:
            text += "###" + video['description'].lower()
        # поиск без перевода
        if translation is None:
            return code_words in text
        # поиск c переводом
        translation = translation.lower()
        return (code_words in text) or (translation in text)

    @staticmethod
    def _not_verbatim_search(video,
                             code_words: str,
                             search_by_description: bool,
                             translation=None) -> bool:
        """
        Функция поиска слов в любом порядке.
        Определяет подходит ли конкретное видео под заданные условия.

        :param video: строка в data_frame со всей информации о конкретном видео
        :param code_words: ключевые слова для поиска
        :param search_by_description:  надо ли искать по описанию
        :param translation: перевод текста,
            если поиск по двум языкам (default None)
        :return: True - видео подходит, False - видео не подходит
        """
        # если нет ключевых слов - подходит любое видео
        if code_words == '':
            return True

        # поиск независимо от регистра
        text = video['title'].lower()
        # поиск по описанию тоже
        if search_by_description:
            text += "###" + video['description'].lower()

        # поиск каждого слова
        words = (code_words.lower()).split()
        words_exist = True
        for word in words:
            if word not in text:
                words_exist = False
                break
        # поиск без перевода или уже нашли по первому языку
        if translation is None or words_exist:
            return words_exist

        # поиск по второму языку, если не нашлось с первым
        translation = (translation.lower()).split()
        translation_exists = True
        for word in translation:
            if word not in text:
                translation_exists = False
                break
        return translation_exists

    @staticmethod
    def _author_search(video,
                       author_name: Union[str, None]) -> bool:
        """
        Функция поиска по автору.
        Определяет подходит ли конкретное видео под заданные условия.

        :param video: строка в data_frame со всей информации о конкретном видео
        :param author_name: ник автора для поиска
        :return: True - видео подходит, False - видео не подходит
        """
        # если не задан автор - подходит любое видео
        if author_name is None or author_name == '':
            return True
        # поиск независимо от регистра
        author_name = author_name.lower()
        return author_name in video['author'].lower()
