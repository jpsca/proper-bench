//! The Actix Web reference app for the Proper benchmarks: the same three
//! routes as `../app`, over the same SQLite file, with sqlx and askama.
//!
//! ```sh
//! cargo build --release && PORT=8123 ./target/release/proper-bench-actix
//! ```
use std::path::PathBuf;

use actix_web::body::MessageBody;
use actix_web::dev::{ServiceRequest, ServiceResponse};
use actix_web::http::header::{HeaderName, HeaderValue};
use actix_web::middleware::{Next, from_fn};
use actix_web::{App, Error, HttpRequest, HttpResponse, HttpServer, Responder, get, web};
use askama::Template;
use serde::Serialize;
use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};

struct Fortune {
    id: i64,
    message: String,
}

#[derive(Template)]
#[template(path = "fortunes.html")]
struct FortunesTemplate {
    fortunes: Vec<Fortune>,
}

#[derive(Serialize)]
struct Message {
    message: &'static str,
}

#[get("/plaintext")]
async fn plaintext() -> impl Responder {
    HttpResponse::Ok()
        .content_type("text/plain; charset=utf-8")
        .body("Hello, World!")
}

#[get("/json")]
async fn json() -> impl Responder {
    web::Json(Message { message: "Hello, World!" })
}

#[get("/fortunes")]
async fn fortunes(pool: web::Data<SqlitePool>) -> actix_web::Result<impl Responder> {
    let rows: Vec<(i64, String)> = sqlx::query_as("SELECT id, message FROM fortune")
        .fetch_all(pool.get_ref())
        .await
        .map_err(actix_web::error::ErrorInternalServerError)?;
    let mut fortunes: Vec<Fortune> = rows
        .into_iter()
        .map(|(id, message)| Fortune { id, message })
        .collect();
    fortunes.push(Fortune { id: 0, message: "Additional fortune added at request time.".into() });
    fortunes.sort_by(|a, b| a.message.cmp(&b.message));
    let html = FortunesTemplate { fortunes }
        .render()
        .map_err(actix_web::error::ErrorInternalServerError)?;
    Ok(HttpResponse::Ok().content_type("text/html; charset=utf-8").body(html))
}

// --- The page route: what a CRUD app's "show" does ---

const SECURITY_HEADERS: [(&str, &str); 5] = [
    ("x-frame-options", "SAMEORIGIN"),
    ("x-xss-protection", "1; mode=block"),
    ("x-download-options", "noopen"),
    ("x-permitted-cross-domain-policies", "none"),
    ("referrer-policy", "strict-origin-when-cross-origin"),
];

/// An origin check for state-changing requests (reads go through) and the
/// security headers on every response of the scope it wraps.
async fn origin_and_security_headers(
    req: ServiceRequest,
    next: Next<impl MessageBody + 'static>,
) -> Result<ServiceResponse<impl MessageBody>, Error> {
    let method = req.method().as_str();
    if !matches!(method, "GET" | "HEAD" | "OPTIONS") {
        let header = |name: &str| req.headers().get(name).and_then(|v| v.to_str().ok());
        let origin = header("origin");
        let sec_fetch_site = header("sec-fetch-site");
        let same = (origin.is_none() && sec_fetch_site.is_none())
            || matches!(sec_fetch_site, Some("same-origin") | Some("none"));
        let same_host = origin
            .and_then(|o| o.split_once("//").map(|(_, host)| host))
            .zip(header("host"))
            .map(|(a, b)| a == b)
            .unwrap_or(false);
        if !same && !same_host {
            return Ok(req.into_response(HttpResponse::Forbidden().finish()).map_into_right_body());
        }
    }
    let mut res = next.call(req).await?;
    let headers = res.headers_mut();
    for (name, value) in SECURITY_HEADERS {
        let name = HeaderName::from_static(name);
        if !headers.contains_key(&name) {
            headers.insert(name, HeaderValue::from_static(value));
        }
    }
    Ok(res.map_into_left_body())
}

struct NavLink {
    id: i64,
    url: String,
    active: bool,
}

#[derive(Template)]
#[template(path = "fortunes/show.html")]
struct ShowTemplate {
    fortune: Fortune,
    index_url: String,
    nav: Vec<NavLink>,
}

#[derive(Template)]
#[template(path = "fortunes/index.html")]
struct IndexTemplate {
    fortunes: Vec<(Fortune, String)>,
    index_url: String,
    nav: Vec<NavLink>,
}

fn nav_links(req: &HttpRequest, current: i64) -> (String, Vec<NavLink>) {
    let index_url = req.url_for_static("fortunes_index").map(|u| u.path().to_string()).unwrap_or_default();
    let nav = (1..=3)
        .map(|n| NavLink {
            id: n,
            url: req.url_for("fortunes_show", [n.to_string()]).map(|u| u.path().to_string()).unwrap_or_default(),
            active: n == current,
        })
        .collect();
    (index_url, nav)
}

async fn pad() -> impl Responder {
    "pad"
}

async fn fortunes_index(req: HttpRequest, pool: web::Data<SqlitePool>) -> actix_web::Result<impl Responder> {
    let rows: Vec<(i64, String)> = sqlx::query_as("SELECT id, message FROM fortune")
        .fetch_all(pool.get_ref())
        .await
        .map_err(actix_web::error::ErrorInternalServerError)?;
    // `fortunes` is taken: the `#[get("/fortunes")]` macro turns that
    // handler into a struct of the same name.
    let items: Vec<(Fortune, String)> = rows
        .into_iter()
        .map(|(id, message)| {
            let url = req.url_for("fortunes_show", [id.to_string()]).map(|u| u.path().to_string()).unwrap_or_default();
            (Fortune { id, message }, url)
        })
        .collect();
    let (index_url, nav) = nav_links(&req, 0);
    let html = IndexTemplate { fortunes: items, index_url, nav }
        .render()
        .map_err(actix_web::error::ErrorInternalServerError)?;
    Ok(HttpResponse::Ok().content_type("text/html; charset=utf-8").body(html))
}

async fn fortunes_show(
    req: HttpRequest,
    path: web::Path<i64>,
    pool: web::Data<SqlitePool>,
) -> actix_web::Result<impl Responder> {
    let id = path.into_inner();
    let row: Option<(i64, String)> = sqlx::query_as("SELECT id, message FROM fortune WHERE id = ?")
        .bind(id)
        .fetch_optional(pool.get_ref())
        .await
        .map_err(actix_web::error::ErrorInternalServerError)?;
    let Some((id, message)) = row else {
        return Ok(HttpResponse::NotFound().finish());
    };
    let (index_url, nav) = nav_links(&req, id);
    let html = ShowTemplate { fortune: Fortune { id, message }, index_url, nav }
        .render()
        .map_err(actix_web::error::ErrorInternalServerError)?;
    Ok(HttpResponse::Ok().content_type("text/html; charset=utf-8").body(html))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let db_path = std::env::var("FORTUNES_DB")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../app/fortunes.db"));
    let pool = SqlitePoolOptions::new()
        .max_connections(64)
        .connect(&format!("sqlite://{}", db_path.display()))
        .await
        .expect("open the fortunes database");
    let port: u16 = std::env::var("PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8123);

    HttpServer::new(move || {
        let mut app = App::new()
            .app_data(web::Data::new(pool.clone()))
            .service(plaintext)
            .service(json)
            .service(fortunes);
        // Fifty other resources, registered before the page, as in an app of that size.
        for n in 0..50 {
            app = app.service(web::resource(format!("/pad{n}/{{id}}")).route(web::get().to(pad)));
        }
        // The middleware wraps the page routes only, like the concerns of
        // Proper's page controller.
        app.service(
            web::scope("/fortunes")
                .wrap(from_fn(origin_and_security_headers))
                .service(web::resource("/all").name("fortunes_index").route(web::get().to(fortunes_index)))
                .service(web::resource("/{id}").name("fortunes_show").route(web::get().to(fortunes_show))),
        )
    })
    .bind(("127.0.0.1", port))?
    .run()
    .await
}
