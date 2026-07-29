const {Command, Flags} = require('@oclif/core')

class ReportCommand extends Command {
  static description = 'Render a report from the most recent crawl'

  static flags = {
    format: Flags.string({description: 'Output format: text, json or html'}),
  }

  async run() {
    this.log('reporting')
  }
}

module.exports = ReportCommand
