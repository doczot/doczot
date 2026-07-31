#!/usr/bin/env node
const { program } = require('commander');

program
  .name('dbtool')
  .description('Database migration helper')
  .version('2.1.0');

program
  .command('migrate')
  .description('Apply all pending migrations to the database')
  .option('--dry-run', 'Print the plan without applying it')
  .action(() => {
    console.log('migrating');
  });

program
  .command('rollback')
  .description('Revert the most recently applied migration')
  .option('--steps <n>', 'How many migrations to revert')
  .action(() => {
    console.log('rolling back');
  });

program
  .command('status')
  .description('Show which migrations have been applied')
  .action(() => {
    console.log('status');
  });

program.parse();
