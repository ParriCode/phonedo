#[cfg(target_arch = "wasm32")]
mod app;

fn main() {
    #[cfg(target_arch = "wasm32")]
    leptos::mount::mount_to_body(app::App);
    #[cfg(not(target_arch = "wasm32"))]
    println!("Usa trunk serve para abrir el panel en el navegador.");
}
