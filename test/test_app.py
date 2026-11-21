from pathlib import Path

from bs4 import BeautifulSoup

from puppetboard import app
from . import MockDbQuery


def test_first_test():
    assert app is not None


def test_no_env(client, mock_puppetdb_environments):
    rv = client.get('/nonexistent/')

    assert rv.status_code == 404


def test_unmatched_url(client, mock_puppetdb_environments):
    rv = client.get('/node/foo/no/such/page')

    assert rv.status_code == 404


def test_offline_mode(client, mocker,
                      mock_puppetdb_environments,
                      mock_puppetdb_default_nodes):
    app.app.config['OFFLINE_MODE'] = True

    query_data = {
        'nodes': [[{'count': 10}]],
        'resources': [[{'count': 40}]],
    }

    dbquery = MockDbQuery(query_data)

    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)
    rv = client.get('/')
    soup = BeautifulSoup(rv.data, 'html.parser')
    assert soup.title.contents[0] == 'Puppetboard'
    for link in soup.find_all('link'):
        assert "//" not in link['href']
        if 'offline' in link['href']:
            rv = client.get(link['href'])
            assert rv.status_code == 200

    for script in soup.find_all('script'):
        if "src" in script.attrs:
            assert "//" not in script['src']

    assert rv.status_code == 200


def test_offline_static(client):
    offline_statics = [
        {
            "content_type": 'css',
            "assets": [
                "static/libs/fomantic-ui/semantic.min.css",
                "static/libs/datatables.net-se/dataTables.semanticui.min.css",
                "static/libs/datatables.net-buttons-se/buttons.semanticui.min.css",
                "static/libs/billboard.js/billboard.min.css",
                "static/css/fonts.css",
            ]
        },
        {
            "content_type": 'javascript',
            "assets": [
                "static/libs/moment.js/moment-with-locales.min.js",
                "static/libs/jquery/jquery.min.js",
                "static/libs/fomantic-ui/semantic.min.js",
                "static/libs/datatables.net/dataTables.min.js",
                "static/libs/datatables.net-buttons/dataTables.buttons.min.js",
                "static/libs/datatables.net-buttons-se/buttons.semanticui.min.js",
                "static/libs/datatables.net-se/dataTables.semanticui.min.js",
                "static/libs/billboard.js/billboard.pkgd.min.js",
                "static/libs/jszip/jszip.min.js",
            ]

        }
    ]

    for category_statics in offline_statics:
        content_type = category_statics.get('content_type')

        for asset in category_statics.get('assets'):
            rv = client.get(asset)

            assert 'Content-Type' in rv.headers
            assert content_type in rv.headers['Content-Type']
            assert rv.status_code == 200


def test_health_status(client):
    rv = client.get('/status')

    assert rv.status_code == 200
    assert rv.data.decode('utf-8') == 'OK'


def test_custom_title(client, mocker,
                      mock_puppetdb_environments,
                      mock_puppetdb_default_nodes):

    default_title = app.app.config['PAGE_TITLE']

    custom_title = 'Dev - Puppetboard'
    app.app.config['PAGE_TITLE'] = custom_title

    query_data = {
        'nodes': [[{'count': 10}]],
        'resources': [[{'count': 40}]],
    }

    dbquery = MockDbQuery(query_data)

    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)
    rv = client.get('/')
    soup = BeautifulSoup(rv.data, 'html.parser')
    assert soup.title.contents[0] == custom_title

    # restore the global state
    app.app.config['PAGE_TITLE'] = default_title


def test_footer_links_to_fork(client, mock_puppetdb_environments, mock_puppetdb_default_nodes):
    page = client.get('/nodes').get_data(as_text=True)
    assert 'href="https://github.com/DennisPohlmann/puppetboard"' in page
    assert 'github.com/voxpupuli/puppetboard"' not in page


def test_app_imports_every_view_module():
    import sys
    views = Path(app.__file__).parent / 'views'
    for module in views.glob('*.py'):
        if module.stem != '__init__':
            assert f'puppetboard.views.{module.stem}' in sys.modules, module.stem


def test_very_compact_css_rule():
    # the class added to DataTables tables must carry the compact padding
    css = (Path(__file__).parent.parent / 'puppetboard' / 'static' / 'css'
           / 'puppetboard.css').read_text()
    assert '.ui.very-compact.table>tbody>tr>td' in css


def test_status_column_shrinks_on_desktop_only():
    css = (Path(__file__).parent.parent / 'puppetboard' / 'static' / 'css'
           / 'puppetboard.css').read_text()
    media = css.split('@media only screen and (min-width: 768px) {\n  #main-table')[1]
    assert 'white-space: nowrap' in media.split('\n}\n')[0]


LONG_ENV = 'feature_JIRA_12345_rework_the_hiera_hierarchy_for_all_datacenters_and_cloud_regions'


def test_environment_menu_shows_long_names_as_tooltip(client, mocker, mock_puppetdb_default_nodes):
    mocker.patch.object(app.puppetdb, 'environments',
                        return_value=[{'name': 'production'}, {'name': LONG_ENV}])
    soup = BeautifulSoup(client.get(f'/{LONG_ENV}/nodes').data, 'html.parser')
    menu = soup.find('div', class_='select-environment')
    # the box cuts the current name with an ellipsis, the tooltip keeps it whole
    assert menu['title'] == LONG_ENV
    assert [i['title'] for i in menu.find_all('div', class_='item')] == [
        'All Environments', 'production', LONG_ENV]


def test_environment_menu_title_for_all_environments(client, mock_puppetdb_environments,
                                                     mock_puppetdb_default_nodes):
    soup = BeautifulSoup(client.get('/nodes').data, 'html.parser')
    assert soup.find('div', class_='select-environment')['title'] == 'All Environments'


def test_environment_menu_css_keeps_long_names_in_view():
    css = (Path(__file__).parent.parent / 'puppetboard' / 'static' / 'css'
           / 'puppetboard.css').read_text()
    box = css.split('.ui.select-environment.dropdown {')[1].split('}')[0]
    assert 'max-width: 22em' in box
    text = css.split('.ui.select-environment.selection.dropdown > .text {')[1].split('}')[0]
    assert 'text-overflow: ellipsis' in text
    menu = css.split('.ui.select-environment.selection.dropdown .menu {\n  left')[1].split('}')[0]
    assert '100vw' in menu
    item = css.split('.ui.select-environment.selection.dropdown .menu > .item {')[1].split('}')[0]
    assert 'overflow-wrap: anywhere' in item
