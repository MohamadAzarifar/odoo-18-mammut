# Commands

usefull commands to use in daily work.

make sure `venv` is activated:

```shell
source venv/bin/activate  
```

install python libraries using this command:

```shell
pip install -i https://mirror-pypi.runflare.com/simple -r requirements.txt  
```

run odoo using the command:

```shell
python odoo-bin -c config/odoo.conf --dev=all 
```

run database on docker using the command:

```shell
docker compose up
```

get container name using the command:

```shell
docker ps
```

execute command on the postgres using the command:

```shell
docker compose exec db psql -U odoo -d postgres -c "SELECT current_user;"  
```

or

```shell
docker exec -it <container-name> createdb -U odoo odoo-test 
```

list all databases:

```shell
docker compose exec db psql -U odoo -l
```

delete a database:

```shell
docker compose exec db dropdb -U odoo odoo-test 
```
