//! The Actix Web reference app for the Proper benchmarks: the same three
//! routes as `../app`, over the same SQLite file, with sqlx and askama.
//!
//! ```sh
//! cargo build --release && PORT=8123 ./target/release/proper-bench-actix
//! ```
use std::path::PathBuf;

use actix_web::{App, HttpResponse, HttpServer, Responder, get, web};
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
        App::new()
            .app_data(web::Data::new(pool.clone()))
            .service(plaintext)
            .service(json)
            .service(fortunes)
    })
    .bind(("127.0.0.1", port))?
    .run()
    .await
}
