# encoding: utf-8
#
# Copyright (C) 2012 Alec Thomas <alec@swapoff.org>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
# Author: Alec Thomas <alec@swapoff.org>

"""
Flask-Injector - A dependency-injection adapter for Flask.

The following example illustrates function and class-based views with
dependency-injection::

    from flask import Flask
    from flask.views import View

    def configure_views(app):
        @app.route("/bar")
        def bar():
            return render("bar.html")


        # Route with injection
        @app.route("/foo")
        @inject(db=sqlite3.Connection)
        def foo(db):
            users = db.execute('SELECT * FROM users').all()
            return render("foo.html")


        @inject(db=sqlite3.Connection)
        class Waz(View):
            def dispatch_request(self):
                users = db.execute('SELECT * FROM users').all()
                return 'waz'

        app.add_url_rule('/waz', view_func=Waz.as_view('waz'))


    def configure(binder):
        config = binder.injector.get(Config)
        binder.bind(
            sqlite3.Connection,
            to=sqlite3.Connection(config['DB_CONNECTION_STRING']),
            scope=request,
        )


    def main():
        app = Flask(__name__)
        app.config.update({'DB_CONNECTION_STRING': ':memory:', })
        injector = Injector(configure)

        preconfigure_app(app, injector)
        configure_views(app)
        postconfigure_app(app, injector)

        app.run()
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import functools

import flask
from werkzeug.local import Local, LocalManager
from injector import Scope, ScopeDecorator, singleton, InstanceProvider
from flask import Config, Request


__author__ = 'Alec Thomas <alec@swapoff.org>'
__version__ = '0.2.0'
__all__ = ['request', 'RequestScope', 'Config', 'Request', ]


def wrap_fun(fun, injector):
    @functools.wraps(fun)
    def wrapper(**kwargs):
        injections = injector.args_to_inject(
            function=fun,
            bindings=fun.__bindings__,
            owner_key=fun.__module__,
        )
        return fun(**dict(injections, **kwargs))

    return wrapper


class RequestScope(Scope):
    """A scope whose object lifetime is tied to a request.

    @request
    class Session(object):
        pass
    """

    def reset(self):
        self._local_manager.cleanup()
        self._locals.scope = {}

    def configure(self):
        self._locals = Local()
        self._local_manager = LocalManager([self._locals])
        self.reset()

    def get(self, key, provider):
        try:
            return self._locals.scope[key]
        except KeyError:
            provider = InstanceProvider(provider.get())
            self._locals.scope[key] = provider
            return provider


request = ScopeDecorator(RequestScope)


def preconfigure_app(app, injector, request_scope_class=RequestScope):
    '''
    Needs to be called right after an application is created (eg. before
    any views, signal handlers etc. are registered).

    :type app: :class:`flask.Flask`
    :type injector: :class:`injector.Injector`
    '''
    def before_request():
        injector.get(request_scope_class).reset()

    app.before_request(before_request)


def postconfigure_app(app, injector, request_scope_class=RequestScope):
    '''
    Needs to be called after all views, signal handlers, etc. are registered.

    :type app: :class:`flask.Flask`
    :type injector: :class:`injector.Injector`
    '''

    for endpoint, view in app.view_functions.items():
        if hasattr(view, '__bindings__'):
            app.view_functions[endpoint] = wrap_fun(view, injector)
        elif (hasattr(view, 'view_class') and
                hasattr(view.view_class.__init__, '__bindings__')):
            current_class = view.view_class

            def cls(**kwargs):
                return injector.create_object(
                    current_class, additional_kwargs=kwargs)

            view.view_class = cls

    def tearing_down(sender, exc=None):
        injector.get(request_scope_class).reset()

    app.teardown_request(tearing_down)

    def configure(binder):
        binder.bind_scope(request_scope_class)
        binder.bind(flask.Flask, to=app, scope=singleton)
        binder.bind(Config, to=app.config, scope=singleton)
        binder.bind(Request, to=lambda: flask.request)

    configure(injector.binder)
