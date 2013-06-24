from injector import inject, Injector
from flask import Flask
from flask.views import View
from nose.tools import eq_

from flask_injector import preconfigure_app, postconfigure_app


def test_injection_in_preconfigured_views():
    def conf(binder):
        binder.bind(str, to="something")
        binder.bind(list, to=[1, 2, 3])

    injector = Injector(conf)
    app = Flask(__name__)

    preconfigure_app(app, injector)

    @app.route('/view1')
    @inject(content=str)
    def view1(content):
        return content

    @inject(content=list)
    class View2(View):
        def dispatch_request(self):
            return str(self.content)

    app.add_url_rule('/view2', view_func=View2.as_view('view2'))

    postconfigure_app(app, injector)

    with app.test_client() as c:
        response = c.get('/view1')
        eq_(response.data, "something")

        response = c.get('/view2')
        eq_(response.data, '[1, 2, 3]')


def test_resets():
    injector = Injector()
    app = Flask(__name__)

    counter = [0]

    class Scope(object):
        def __init__(self, injector):
            pass

        def reset(self):
            counter[0] += 1

    preconfigure_app(app, injector, request_scope_class=Scope)

    @app.route('/')
    def index():
        eq_(counter[0], 1)
        return 'asd'

    postconfigure_app(app, injector, request_scope_class=Scope)

    eq_(counter[0], 0)

    with app.test_client() as c:
        c.get('/')

    eq_(counter[0], 2)
