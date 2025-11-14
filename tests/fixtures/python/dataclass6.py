def test_template_filter_with_template(app, client):
    bp = flask.Blueprint("bp", __name__)

    @bp.app_template_filter()
    def super_reverse(s):
        return s[::-1]

    app.register_blueprint(bp, url_prefix="/py")

    @app.route("/")
    def index():
        return flask.render_template("template_filter.html", value="abcd")

    rv = client.get("/")
    assert rv.data == b"dcba"


def test_template_filter_after_route_with_template(app, client):
    @app.route("/")
    def index():
        return flask.render_template("template_filter.html", value="abcd")

    bp = flask.Blueprint("bp", __name__)

    @bp.app_template_filter()
    def super_reverse(s):
        return s[::-1]

    app.register_blueprint(bp, url_prefix="/py")
    rv = client.get("/")
    assert rv.data == b"dcba"


