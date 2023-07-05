COMPOSE := docker-compose -f docker-compose.yml

copy_cert:
	@docker cp kibana:/usr/share/kibana/config/certs/ca/ca.crt ./backend/ca.crt

clean:
	@$(COMPOSE) down -v
	@rm ./backend/ca.crt

populate_elastic:
	@echo Populating Elasticsearch with data..
	@$(COMPOSE) exec bilara-backend python -c "from search.search import Search; Search()"
	@echo Elasticsearch has been populated!

up:
	@$(COMPOSE) up -d
	@make copy_cert
	@make populate_elastic

build:
	@$(COMPOSE) up --build -d
	@make copy_cert
	@make populate_elastic

down:
	@$(COMPOSE) down
