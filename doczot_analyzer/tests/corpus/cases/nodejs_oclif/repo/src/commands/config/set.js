const {Command} = require('@oclif/core')

class ConfigSetCommand extends Command {
  static description = 'Set a configuration value'

  async run() {
    this.log('setting config')
  }
}

module.exports = ConfigSetCommand
