COMPOSE := docker-compose -f docker-compose.yml

copy_cert:
	@docker cp kibana:/usr/share/kibana/config/certs/ca/ca.crt ./backend/ca.crt

clean:
	@$(COMPOSE) down -v
	@rm ./backend/ca.crt

up:
	@$(COMPOSE) up -d
	@make copy_cert

build:
	@$(COMPOSE) up --build -d
	@make copy_cert

down:
	@$(COMPOSE) down
