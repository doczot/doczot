const {Command, Flags} = require('@oclif/core')

class CrawlCommand extends Command {
  static description = 'Crawl a site and record every link found'

  static flags = {
    depth: Flags.integer({description: 'How many levels deep to follow links'}),
    concurrency: Flags.integer({description: 'Number of parallel requests'}),
  }

  async run() {
    this.log('crawling')
  }
}

module.exports = CrawlCommand
