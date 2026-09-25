class BenchController < ApplicationController
  # No sessions or CSRF for these routes, like the other apps.
  skip_forgery_protection

  def plaintext
    render plain: "Hello, World!"
  end

  def json
    render json: { message: "Hello, World!" }
  end

  def fortunes
    rows = Fortune.pluck(:id, :message).map { |id, message| [id, message] }
    rows << [0, "Additional fortune added at request time."]
    @fortunes = rows.sort_by { |_, message| message }
  end
end
