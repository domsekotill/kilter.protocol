[![gitlab-ico]][gitlab-link]
[![licence-mpl20]](/LICENCE.txt)
[![pre-commit-ico]][pre-commit-link]
[![pipeline-status]][pipeline-report]
[![coverage status]][coverage report]


Kilter Protocol
===============

Kilter is a framework for writing [mail filters](#sendmail-filters) (known as "milters") 
compatible with Sendmail and Postfix MTAs.  Unlike many previous milter implementations in 
Python it is not simply bindings to the `libmilter` library (originally from the Sendmail 
project).  The framework aims to provide Pythonic interfaces for implementing filters, 
including leveraging coroutines instead of `libmilter`'s callback-style interface.

The `kilter.protocol` package contains the parsers and filter state machine for the 
communications protocol used between the Mail Transfer Agents (MTA) and filters.

Users looking for something as simple to use as [`libmilter`](#libmilter) should take a look 
at [`kilter.service`][].

What is understood about the wire protocol is documented in 
[Wire Protocol](https://kilter.doc.kodo.org.uk/kilter.protocol/wire-protocol/).

[`kilter.service`]: https://code.kodo.org.uk/kilter/kilter.service


Sendmail Filters
----------------

The Sendmail filter (milter) API facilitates communication between a Mail Transfer Agent 
(MTA) and arbitrary filters running as external services.  These filters can perform 
a number of operations on received and outgoing mail, such as: virus scanning; checking 
senders' reputations; signing outgoing mail; and verifying signatures of incoming mail.

While the protocol was originally for filtering mail through a Sendmail MTA, Postfix has 
also reverse engineered the protocol and supports most filters made for Sendmail.


`libmilter`
-----------

Historically filters used the `libmilter` library supplied by the Sendmail project to handle 
all aspects of communication with an MTA.  Filters simply registered callbacks for various 
events then started the library's main loop. This approach makes implementing simple filters 
in C easy for users, but makes writing "Pythonic" filters difficult, especially when a user 
wishes to make use of async/await features.

Use of `libmilter` to implement filters is almost universal as it is a black-box; the 
on-the-wire protocol used is undocumented and subject to change between versions, which 
makes writing a third-party parser difficult.


[gitlab-ico]:
  https://img.shields.io/badge/GitLab-code.kodo.org.uk-blue.svg?logo=gitlab
  "GitLab"

[gitlab-link]:
  https://code.kodo.org.uk/kilter/kilter.protocol
  "Kilter Protocol at code.kodo.org.uk"

[pre-commit-ico]:
  https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
  "Pre-Commit: enabled"

[pre-commit-link]:
  https://github.com/pre-commit/pre-commit
  "Pre-Commit at GitHub.com"

[licence-mpl20]:
  https://img.shields.io/badge/Licence-MPL--2.0-blue.svg
  "Licence: Mozilla Public License 2.0"

[pipeline-status]:
  https://code.kodo.org.uk/kilter/kilter.protocol/badges/main/pipeline.svg

[pipeline-report]:
  https://code.kodo.org.uk/kilter/kilter.protocol/pipelines/latest
  "Pipelines"

[coverage status]:
  https://code.kodo.org.uk/kilter/kilter.protocol/badges/main/coverage.svg

[coverage report]:
  https://code.kodo.org.uk/kilter/kilter.protocol/-/jobs/artifacts/main/file/results/coverage/index.html?job=Unit+Tests


Usage
=====

Most users will be looking for an asynchronous API using Python coroutines: this is 
available with the [`kilter.service`][] package.  The protocol handlers provided by this 
package support asynchronous operation but does not handle any IO, thus have no awaitable 
entrypoints. Instead a service that handles socket communication with MTAs passes bytes from 
a socket to a protocol handler, which returns event objects.  Some of these events instruct 
the service to pass bytes back to the socket, others are actionable in ways that are 
implementation specific.  When an implementation wants to communicate with an MTA, it 
registers messages with the protocol handler, which again returns event objects.
