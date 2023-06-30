COMPOSE := docker-compose -f docker-compose.yml

copy_cert:
	@docker cp kibana:/usr/share/kibana/config/certs/ca/ca.crt ./backend/ca.crt

clean:
	@$(COMPOSE) down -v
	@rm ./backend/ca.crt

app:
	@$(COMPOSE) up
	@make copy_cert

