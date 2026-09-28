FROM mysql:8.0.39

# Defaults match local_db.py. Override at runtime with -e if needed.
ENV MYSQL_ROOT_PASSWORD=root \
    MYSQL_DATABASE=testdb \
    MYSQL_USER=testuser \
    MYSQL_PASSWORD=test123

EXPOSE 3306
