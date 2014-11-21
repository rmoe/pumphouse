var Config = require('./config');
var Listener = require('./events');
var API = require('./api');

var events = new Listener(Config.endpoint + '/events');
var pumphouse = new API(Config.endpoint);

var cases = Config.cases,
    i = 0,
    completed = true,
    c,
    timer;

// Async tests runner
setInterval(function() {
    if (completed) {
        cycles = 0;
        if (i >= cases.length) {
            console.log('Tests execution completed');
            process.exit(code=0);
        }
        c = require('./case_' + cases[i++]);
        c.testcase.run(pumphouse, events);
    }
    completed = c.testcase.completed;
    if (cycles++ > Config.timeout) {
        console.error('Timed out!');
        process.exit(code=1);
    }
    cycles++;
}, 1000);

