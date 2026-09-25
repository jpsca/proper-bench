# Workers are processes; threads per worker come from the harness.
workers Integer(ENV.fetch("WEB_CONCURRENCY", 1))
threads_count = Integer(ENV.fetch("RAILS_MAX_THREADS", 4))
threads threads_count, threads_count
environment ENV.fetch("RAILS_ENV", "production")
preload_app!
