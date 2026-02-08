# MQTT Broker Configuration

## Files

- **config.xml** - HiveMQ broker configuration (port, listeners)
- **logback-dev.xml** - Development logging (verbose, shows connections/subscriptions)
- **logback-prod.xml** - Production logging (minimal, errors/warnings only)

## Logging Levels

### Development (logback-dev.xml) - Current Default
- **Level:** DEBUG
- **Shows:** Connections, disconnections, subscriptions, unsubscribes, session events
- **Use for:** Development, debugging, learning MQTT
- **Performance:** Slightly slower, larger logs

### Production (logback-prod.xml)
- **Level:** WARN
- **Shows:** Only errors and critical warnings
- **Use for:** Production deployment
- **Performance:** Faster, minimal logs

## Switching Between Configs

1. Edit `docker-compose.yml`
2. Change the logback volume mount:
   ```yaml
   # Development (current):
   - ./config/mqtt/logback-dev.xml:/opt/hivemq/conf/logback.xml:ro
   
   # Production:
   - ./config/mqtt/logback-prod.xml:/opt/hivemq/conf/logback.xml:ro
   ```
3. Restart broker:
   ```bash
   npm run docker:down
   npm run docker:up
   ```

## Viewing Logs

```bash
# Live logs (follows new messages)
npm run docker:logs

# Last 50 lines
docker compose logs --tail=50 mqtt-broker

# Since last 5 minutes
docker compose logs --since=5m mqtt-broker
```

## Note

**You must restart the container** after changing the logging configuration for changes to take effect.
