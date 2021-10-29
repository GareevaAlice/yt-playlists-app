from main import app
from config import yt_api_key_file_path, dl_key_file_path, client_secret

from flask import render_template, redirect, url_for

from app.clients.YouTubePlaylistsHandler import YouTubePlaylistsHandler
from app.clients.DataFrameSearcher import DataFrameSearcher
from app.forms import UrlOrIdForm, SearchForm

# Класс для информации о плейлисте.
# yt_api_key_file_path - путь к файлу,
# где лежит api-key для доступа к YouTube Data API v3
yt_playlists_handler = \
    YouTubePlaylistsHandler.yt_api_key_from_file(yt_api_key_file_path,
                                                 client_secret)


# -----------------------------------------------------------
# Главная страница.
@app.route("/", methods=['GET', 'POST'])
def main():
    # если пользователь авторизован,
    # то перенаправить на главную страницу для авторизованных пользователей
    if 'credentials' in session:
        return redirect('oauth_main')

    form = UrlOrIdForm()
    if form.validate_on_submit():
        url_or_id = form.url_or_id.data
        try:  # получаем информацию о каждом видео из плейлиста
            data_frame = yt_playlists_handler(url_or_id)
        # невозможно получить доступ
        except yt_playlists_handler.CannotGetError:
            form.url_or_id.errors = \
                (yt_playlists_handler.CannotGetError.message, '')
        # что-то пошло не так
        except yt_playlists_handler.UndefinedError:
            form.url_or_id.errors = \
                (yt_playlists_handler.UndefinedError.message, '')
        else:
            yt_playlists_handler.df_searcher = \
                DataFrameSearcher(data_frame, dl_key_file_path)
            #  переходим на страницу поиска, если все хорошо
            playlist_id = yt_playlists_handler.get_playlist_id(url_or_id)
            return redirect(url_for('search',
                                    playlist_id=playlist_id))
    can_OAuth = (yt_playlists_handler.client_secret is not None)
    return render_template("main.html",
                           form=form,
                           # пользователь не авторизован
                           OAuth=False,
                           # может ли пользователь работать с OAuth
                           can_OAuth=can_OAuth,
                           title='Главная')


# Страница поиска.
# playlist_id - id плейлиста, по которому производится поиск
@app.route("/search/<playlist_id>", methods=['GET', 'POST'])
def search(playlist_id):
    # проверка, что мы можем работать с плейлистом с данным playlist_id
    if yt_playlists_handler.df_searcher is None \
            or yt_playlists_handler.work_playlist_id is None \
            or yt_playlists_handler.work_playlist_id != playlist_id:
        return redirect('/')

    playlist_url = f'https://www.youtube.com/playlist?list={playlist_id}'
    form = SearchForm()
    results = dict()
    translation = None
    nothing_error = None
    if form.validate_on_submit():
        try:  # производим поиск
            verbatim_search = form.search_type.data == "verbatim_search"
            results = \
                yt_playlists_handler.df_searcher(
                    code_words=form.code_words.data,
                    author_name=form.author.data,
                    search_by_description=form.search_by_description.data,
                    verbatim_search=verbatim_search,
                    bilingual_search=form.bilingual_search.data)
            if results['data_frame'].empty:  # ничего не нашли
                raise yt_playlists_handler.df_searcher.NothingError
        # ничего не нашли
        except yt_playlists_handler.df_searcher.NothingError:
            nothing_error = \
                yt_playlists_handler.df_searcher.NothingError.message
        # что-то пошло не так с API при переводе
        except yt_playlists_handler.df_searcher.text_translator.UndefinedError:
            form.bilingual_search.errors = \
                (yt_playlists_handler.df_searcher.text_translator.
                 UndefinedError.message, '')
        # невозможно перевести текст
        except yt_playlists_handler.df_searcher.text_translator.NothingError:
            form.bilingual_search.errors = \
                (yt_playlists_handler.df_searcher.text_translator.
                 NothingError.message, '')
        if results:
            translation = results['translation']
            results = results['data_frame'].to_dict('index')
    return render_template("search.html",
                           form=form,
                           playlist_url=playlist_url,
                           results=results,
                           translation=translation,
                           nothing_error=nothing_error,
                           title='Поиск')


# -----------------------------------------------------------
# Главная страница, но для авторизованных пользователей с помощью OAuth.
# -----------------------------------------------------------


@app.route("/oauth_main", methods=['GET', 'POST'])
def oauth_main():
    # если не настроен OAuth, то перенаправить на главную страницу
    if yt_playlists_handler.client_secret is None:
        return redirect('main')
    # если пользователь не авторизован,
    # то перенаправить на главную страницу для обычных пользователей
    if 'credentials' not in session:
        return redirect('main')

    form = UrlOrIdForm()
    if form.validate_on_submit():
        url_or_id = form.url_or_id.data
        # получаем информацию о каждом видео из плейлиста,
        # учитывая, что пользователь авторизован
        try:
            data_frame = yt_playlists_handler(url_or_id, oauth=True)
        # что-то пошло не так (не получилось получить доступ)
        except yt_playlists_handler.OAuthUndefinedError:
            form.url_or_id.errors = \
                (yt_playlists_handler.OAuthUndefinedError.message, '')
        else:
            yt_playlists_handler.df_searcher = \
                DataFrameSearcher(data_frame, dl_key_file_path)
            #  переходим на страницу поиска, если все хорошо
            playlist_id = yt_playlists_handler.get_playlist_id(url_or_id)
            return redirect(url_for('search',
                                    playlist_id=playlist_id))
    return render_template("main.html",
                           form=form,
                           # пользователь авторизован
                           OAuth=True,
                           # пользователь может работать с OAuth
                           can_OAuth=True,
                           title='Главная')


# -----------------------------------------------------------
# Страницы для авторизации пользователя в Google Account с помощью OAuth.
# (https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps)
# Для работы надо провести настройку в консоле API.
# Подробнее написано в README.md.
# -----------------------------------------------------------

from flask import session, request
import google_auth_oauthlib.flow

# Возможности авторизации (аккаунт доступен только для чтения).
scopes = ["https://www.googleapis.com/auth/youtube.readonly"]


# Авторизация пользователя.
@app.route('/oauth_authorize')
def oauth_authorize():
    # если не настроен OAuth, то перенаправить на главную страницу
    if yt_playlists_handler.client_secret is None:
        return redirect('main')
    # если уже авторизован, то выйти из аккаунта и авторизоваться заново
    if 'credentials' in session:
        del session['credentials']

    # создаем flow для работы с OAuth
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        yt_playlists_handler.client_secret,
        scopes=scopes)

    # URI для перенаправления после авторизации
    # Данный URI должен соответствовать
    # одному из авторизованных "redirect URIs",
    # которые настраиваются в консоли API > Credentials > OAuth 2.0 Client IDs
    # для конкретного web-приложения
    # В нашем случае: "http://localhost:5000/oauth_callback"
    flow.redirect_uri = url_for('oauth_callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # получения токен доступа
        # без повторных запросов разрешения у пользователя
        access_type='offline',
        include_granted_scopes='true')

    # сохраняем состояние, чтобы обратный запрос (oauth_callback)
    # мог проверить ответ сервера аутентификации.
    session['state'] = state

    # Отправляем пользователя на страницу авторизации
    return redirect(authorization_url)


# Проверка подключения, окончательная авторизация.
@app.route('/oauth_callback')
def oauth_callback():
    # если не настроен OAuth, то перенаправить на главную страницу
    if yt_playlists_handler.client_secret is None:
        return redirect('main')
    # если пользователь не пытался авторизоваться,
    # то перенаправить на главную страницу для обычных пользователей
    if 'state' not in session:
        return redirect('main')

    state = session['state']

    # создаем flow для работы с OAuth и подтверждения авторизации
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        yt_playlists_handler.client_secret,
        scopes=scopes,
        state=state)
    flow.redirect_uri = url_for('oauth_callback', _external=True)

    # используем ответ сервера авторизации для получения токенов OAuth
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    # получаем учетные данные пользователя и сохраняем их в сеанс.
    credentials = flow.credentials
    session['credentials'] = {'token': credentials.token,
                              'refresh_token': credentials.refresh_token,
                              'token_uri': credentials.token_uri,
                              'client_id': credentials.client_id,
                              'client_secret': credentials.client_secret,
                              'scopes': credentials.scopes}

    # отправляем пользователя на главну страницу
    # для авторизованных пользователей
    return redirect(url_for('oauth_main'))


# -----------------------------------------------------------

# Если страницы не существует - перенаправляем на главную.
@app.errorhandler(404)
def page_not_found(e):
    return redirect('/')
