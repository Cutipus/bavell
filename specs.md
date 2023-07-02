# description

## schedule - logic based
  - status based: if online
  - date based: if on specific date
  - weekly based: if on specific day
  - clock based: if on specific hourly interval
  - interval based: if interval passed
  - request based: user requested

## a questionaire comes in various forms
  - session
    - user input to start
    - send stream of questionaires according to session spec
    - gather statistics on success rate and measure time
    - gather session log from user
  - single question
    - passive card - non interactive, word and spoilered definition, association or sentence
    - american style - choose the correct definition of the word 
    - reverse american - choose correct word based on definition
  - tasks
    - write sentence using the word
    - write an association to the word

# examples

## date based schedule of a working person
```
sunday -> friday, 8:00 -> 13:00, every 1hr
  session, time limit 1m
    random order, default unit 1 -> 10
      1 passive card | unit 1 -> 3
      5 american style | unit 5 -> 10
      2 reverse american | unit 10
      1 passive card
    default unit 3
      2 sentence
      3 associations
```

## whenever user is online
```
online, every 30m
  1 passive card | unit 1 -> 5
```


