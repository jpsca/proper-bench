Rails.application.routes.draw do
  get "plaintext", to: "bench#plaintext"
  get "json", to: "bench#json"
  get "fortunes", to: "bench#fortunes"
end
