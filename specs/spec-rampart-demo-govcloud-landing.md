# Rampart GovCloud Landing View Specification

## Philosophy

This specification defines the first landing-page system visualization for the Rampart demo: a TAP / git-serious deployment as it would run inside AWS GovCloud, drawn at the **multi-account elevation**. The deployment is a stand-in for a hosted git-serious service inside a multi-account FedRAMP-shaped hosting environment. The hosting environment is built in the `highbar-hosting` project (criticalsecllc repository); the product is git-serious (unified-systems-tap organization).

The view has to be *true to the grid*. Every box is a node the grid holds and every line is an edge the grid holds. Where the story wants an arrow the grid cannot yet carry, the arrow is **left out and recorded as a gap** below. It is not drawn from an edge minted for the picture. That rule is the point of the exercise: the gaps found here are the work list for the plugins that own them.

The view is also the first elevation. A later spec covers zooming into each component (high availability, subnets and security groups, VPC endpoints and egress). This one fixes only what is on the top view and leaves hooks for what comes after.

Provenance of the facts below: edge and node-type availability was read from the edge definitions and models of `aws-core-tap`, `github-core-tap`, `git-core-tap`, `identity-core-tap` and `computing-core-tap` at their default branches on 2026-10-13. It was read, not run. The implementer verifies each claimed edge with the plugins loaded before relying on it.

## Goals

|   |   |   |
| :---: | --- | --- |
| 1. | Three Human Flows | Customers' traffic comes in from the left, code and containers come in from the right, and administration comes in from below. All three are visible and meet at the product account. |
| 2. | Production-Shaped | The product account looks like a production deployment: DNS, edge protection, a load balancer, containers across availability zones, a highly available database with backups, secrets and keys. |
| 3. | Account Separation | The support accounts are visibly separate from the product account and visibly receive its evidence (logs, findings, backups). |
| 4. | Grid-True | Everything drawn is backed by existing nodes and edges; everything else is a recorded gap. |
| 5. | Zoom-Ready | The top view leaves room for the elevation system to open each component later without redrawing the page. |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-demo-govcloud-view | [Landing View](#landing-view) | Proposed | The landing page opens on a full-page multi-account projection of the git-serious deployment in GovCloud. |
| req-demo-govcloud-layout | [Spatial Layout](#spatial-layout) | Proposed | Customers left, product account centre, deployment path right, support accounts in a row along the bottom, administrator below. |
| req-demo-govcloud-product | [Product Account](#product-account) | Proposed | DNS, edge, load balancer, containers, database, secrets, keys and the deploy system, with the containers at the centre. |
| req-demo-govcloud-deploy | [Deployment Path](#deployment-path) | Proposed | Developer to laptop to GitHub to GHCR to ECR to the deploy step to the containers. |
| req-demo-govcloud-support | [Support Accounts](#support-accounts) | Proposed | Five support accounts in a horizontal row beneath the product account. |
| req-demo-govcloud-admin | [Administrator](#administrator) | Proposed | A representative infrastructure administrator and their computer below the support row. |
| req-demo-govcloud-grid-true | [Grid-True Edges](#grid-true-edges) | Proposed | Every drawn relationship maps to an existing edge; the rest are recorded gaps. |
| req-demo-govcloud-gaps | [Recorded Gaps](#recorded-gaps) | Proposed | The arrows, nodes and edge splits this view needs and the grid does not yet have. |
| req-demo-govcloud-population | [Population](#population) | Proposed | The nodes are populated as data through the owning plugins, not by bespoke code. |
| req-demo-govcloud-deferred | [Deferred To The Zoom View](#deferred-to-the-zoom-view) | Proposed | High availability, egress and endpoints, agents, cross-region backup. |

### Landing View
----
RID: `req-demo-govcloud-view`

Status: `Proposed`

The landing page opens directly into a full-page projection of the whole deployment, at the elevation where the unit is an AWS account. It needs no scrolling at the demo screen size.

#### Implementation
Built on the tap_viz runtime as data: a projection, arrangements and layout configuration, not new geometry code. The `create-layout` skill is the entry point: it asks first whether the scene can be expressed as data, and for this view it should be.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-view-1 | Opens On The Projection | Proposed | The landing page opens on the multi-account projection with no setup step. | |
| req-demo-govcloud-view-2 | Fits One Screen | Proposed | The whole view is legible at the demo display size without scrolling or panning. | |
| req-demo-govcloud-view-3 | Elements Are Navigable | Proposed | Each account and each major component is a clickable element, so a later zoom view has something to attach to. | The zoom itself is out of scope here. |

### Spatial Layout
----
RID: `req-demo-govcloud-layout`

Status: `Proposed`

The layout expresses the three flows as three directions meeting at the centre.

| Area | Placement |
| --- | --- |
| Customers and their computers | Far left, centred vertically. |
| Product account | Centre of the screen. |
| Route53 | **Upper-left corner of the product account**, so the customer's DNS lookup runs diagonally up and to the right while the main traffic runs horizontally. |
| Main request path | Left to right on one horizontal line: customer computer, internet gateway, VPC, WAF, load balancer, containers. |
| git-serious containers | At the centre of the whole visualization. |
| Deployment path | To the right of the containers, reading right to left toward them. |
| Support accounts | A horizontal row aligned along the bottom edge of the product account. |
| Administrator and computer | Below the support row. |

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-layout-1 | Containers Are Central | Proposed | The git-serious web and worker containers sit at the centre of the view. | |
| req-demo-govcloud-layout-2 | Customer Flow Is Horizontal | Proposed | The request path from the customer computer to the containers runs on a single horizontal line. | |
| req-demo-govcloud-layout-3 | Route53 Upper-Left | Proposed | Route53 is placed in the upper-left of the product account. | |
| req-demo-govcloud-layout-4 | Deployment Enters From The Right | Proposed | The deployment path enters the product account from the right. | |
| req-demo-govcloud-layout-5 | Support Row Along The Bottom | Proposed | The support accounts form one horizontal row along the bottom of the product account. | |
| req-demo-govcloud-layout-6 | Administrator Below | Proposed | The administrator and their computer sit below the support row. | |
| req-demo-govcloud-layout-7 | Room For Agents | Proposed | A slot is left beside the developer and beside the administrator for agent actors, left empty for now. | See Deferred. |

### Product Account
----
RID: `req-demo-govcloud-product`

Status: `Proposed`

The account where git-serious runs. It holds, from the customer side inward:

- **DNS:** a Route53 public hosted zone (public zones are supported in GovCloud as of April 2025, per the AWS announcement linked below).
- **Edge:** an internet gateway on the VPC, AWS WAF in front of the load balancer, an ACM certificate for TLS.
- **Network:** one VPC with public, private and isolated subnet tiers across two availability zones. The load balancer sits in the public tier, the containers in the private tier, the database in the isolated tier.
- **Containers:** an ECS cluster running the git-serious web service and the worker service (the task queue, split from the web container; see Deferred).
- **Data:** an RDS Postgres instance, Multi-AZ, replacing the database container of a development stack.
- **Secrets and keys:** Secrets Manager secrets the containers read, and KMS keys encrypting the database, the secrets and the logs.
- **Delivery:** an ECR repository and the deploy step (GitHub Actions through an OIDC trust), both inside the account.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-product-1 | Request Path Present | Proposed | The nodes of the request path (internet gateway, VPC, load balancer, ECS service) are shown in order. | |
| req-demo-govcloud-product-2 | Database Shows HA | Proposed | The RDS instance is shown as Multi-AZ at this elevation, without drawing the standby. | The standby is a zoom-level detail. |
| req-demo-govcloud-product-3 | Secrets And Keys Shown | Proposed | Secrets Manager and KMS appear in the product account. | |
| req-demo-govcloud-product-4 | Subnet Tiers Shown | Proposed | The public, private and isolated tiers are visible as containers of their members. | |
| req-demo-govcloud-product-5 | WAF And Certificate Shown | Proposed | A WAF and an ACM certificate appear on the load balancer. | The WAF has no node type yet; see Recorded Gaps. |

#### Future
Public-zone support in GovCloud should be re-checked when the demo environment is stood up; the announcement is dated 2025.

### Deployment Path
----
RID: `req-demo-govcloud-deploy`

Status: `Proposed`

Right to left toward the containers: developer, developer's laptop, GitHub.com (repository and workflow run), GHCR, ECR in the product account, the deploy step, the ECS service. GHCR does not feed production directly: a FedRAMP-shaped environment mirrors images into its own registry, which is why ECR is on the path.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-deploy-1 | Path Is Complete | Proposed | Every hop from developer to ECS service is shown as a node. | |
| req-demo-govcloud-deploy-2 | ECR Is On The Path | Proposed | ECR sits between GHCR and the service. | |
| req-demo-govcloud-deploy-3 | Deploy Lives In The Product Account | Proposed | The deploy step is inside the product account. | Ruled by the maintainer, 2026-10-13. |

### Support Accounts
----
RID: `req-demo-govcloud-support`

Status: `Proposed`

Five accounts in a row beneath the product account. What each holds will grow as the hosting environment is built; the first set is:

| Account | Holds |
| --- | --- |
| org / management | AWS Organizations, service control policies, Identity Center |
| security | GuardDuty, Security Hub, Config aggregator, Inspector |
| log archive | CloudTrail organization trail, flow logs, Config delivery, in storage the product account cannot alter |
| backup | AWS Backup vault receiving the database's backups |
| remote-access | Placeholder for Teleport; created now and left empty |

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-support-1 | Five Accounts In A Row | Proposed | The org/management, security, log archive, backup and remote-access accounts appear as one horizontal row. | |
| req-demo-govcloud-support-2 | Evidence Reaches The Support Accounts | Proposed | The product account is connected downward to the security, log archive and backup accounts, so logs, findings and backups visibly leave it. | Only where the edge exists; see Recorded Gaps. |
| req-demo-govcloud-support-3 | Remote-Access Is Named | Proposed | The remote-access account is present and named `remote-access`. | |

### Administrator
----
RID: `req-demo-govcloud-admin`

Status: `Proposed`

A representative infrastructure administrator and their computer, below the support row. Console and identity reach the accounts through Identity Center; sessions into the environment go through the remote-access account. The product account is not reached by direct login.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-admin-1 | Administrator Shown | Proposed | An administrator and their computer appear below the support row. | |
| req-demo-govcloud-admin-2 | Identity Center Link | Proposed | The administrator is linked toward the org/management account through the identity edges that exist. | The remote-access session path is a recorded gap. |

### Grid-True Edges
----
RID: `req-demo-govcloud-grid-true`

Status: `Proposed`

Every line on the page is an edge the grid holds. An arrow that would need a new edge is not drawn. Per the maintainer's ruling of 2026-10-13, the view starts from the edges that exist, and anything that looks like a flow or an action modelled as an edge is raised for discussion, not minted. The proposed general mechanism for flows, the compound edge, is recorded in `tap_grid/specs/spec-grid-edge.md` (Future).

Likely backed by existing edge types (from reading the edge definitions; verify when populating):

| Drawn relationship | Existing edge | Plugin |
| --- | --- | --- |
| account contains VPC, subnets | `HOSTS_VPC`, `HOSTS_SUBNET` (from the account region) | aws_core |
| load balancer, service, database in a subnet | `RESIDES_IN_SUBNET` | aws_core |
| internet gateway on the VPC | `ATTACHED_TO_VPC` | aws_core |
| cluster runs the service | `RUNS_SERVICE` | aws_core |
| database, secrets, logs encrypted with a key | `ENCRYPTED_WITH_KEY` | aws_core |
| service writes logs; trail and Config deliver to buckets | `WRITES_LOGS` (being split, see below) | aws_core |
| Route53 zone points at CloudFront today | `ROUTES_TRAFFIC` (being split, see below) | aws_core |
| GuardDuty / Security Hub report to the delegated administrator | `REPORTS_TO_ADMINISTRATOR`, `DELEGATES_TO_ACCOUNT` | aws_core |
| Identity Center access to accounts | account assignment and permission set edges | aws_core |
| repository trusts AWS through OIDC | `FEDERATES_VIA_PROVIDER` | github_core |
| repository, workflow, run, package version | `OWNS_REPO`, `DEFINES_WORKFLOW`, `EXECUTES_WORKFLOW`, `BUILDS_PACKAGE_VERSION`, `PUBLISHES_PACKAGE_VERSION` | github_core |
| administrator is a person | `HELD_BY_HUMAN` | identity_core |

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-grid-true-1 | Every Line Has An Edge | Proposed | Each line in the projection is rendered from an edge in the grid; the projection has no hand-drawn connectors. | |
| req-demo-govcloud-grid-true-2 | Gaps Are Not Faked | Proposed | A relationship with no edge is absent from the page, not approximated with a different edge type. | |
| req-demo-govcloud-grid-true-3 | Mapping Is Verified | Proposed | Before population, each row of the table above is confirmed against the loaded plugins, and any row that does not hold is moved to Recorded Gaps. | |

### Recorded Gaps
----
RID: `req-demo-govcloud-gaps`

Status: `Proposed`

What the view wants and the grid does not yet have. These are inputs to other work and are not built by this spec.

**Flows (wait for the compound edge, `spec-grid-edge.md` Future):**

1. Customer computer to the internet gateway and the load balancer (the request path), and the DNS lookup from the customer to Route53.
2. Service to database.
3. Service reading secrets.
4. Image delivery: GHCR to ECR, and ECR to the running service.
5. Database backups to the backup vault.
6. Administrator sessions through remote-access into an account, and a developer's push from a laptop to GitHub.

**Node types missing in aws_core:** AWS Backup (vault and plan), AWS WAF (web ACL). The ACM certificate and load balancer exist but nothing links a load balancer to its certificate; load balancer to target group to service is also unmodelled (`ATTACHED_TO_TARGET` and `APPLIES_TO_TARGET` are Organizations and Control Tower edges).

**Edges being split, one specific edge per mechanism** (no previous deployments to support):

- `ROUTES_TRAFFIC` -> unified-systems-com/aws-core-tap#93, which includes the new Route53 alias to load balancer edge this view needs.
- `WRITES_LOGS` -> unified-systems-com/aws-core-tap#92, which separates function, container, audit-trail and Config delivery.

Until those land the view can use the existing types where they apply.

**Elsewhere:**

- Web-tier high availability: unified-systems-com/tap#1020 (epic).
- A worker service split from the web container is part of that epic (unified-systems-com/tap#1016).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-gaps-1 | Gaps Are Tracked | Proposed | Each gap above has a home (an issue, a spec section, or this list), and none is worked around inside the projection. | |
| req-demo-govcloud-gaps-2 | No Ad Hoc Flow Edges | Proposed | No plugin or instance data mints an edge to stand for a flow while the compound edge is unbuilt. | |

### Population
----
RID: `req-demo-govcloud-population`

Status: `Proposed`

The accounts, networks, services and people on the page are populated as **data** by the plugins that own each type, through a GRIFT batch, plus the instance's Pages, Searches, panel configuration and layout hints. No bespoke code lives in the instance. A gap in a plugin is fixed in that plugin's repository, not worked around in the instance.

The data models a *declared* deployment; it is not read from a live GovCloud environment. It should say so (provenance as seeded, not collected) so the page never presents modelled data as observed. When the highbar-hosting environment exists, the same view is the natural target for real collection.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-demo-govcloud-population-1 | Data Only | Proposed | Populating the view adds data and configuration, with no new Python in the instance plugin. | |
| req-demo-govcloud-population-2 | Provenance Is Honest | Proposed | Seeded nodes are distinguishable from collected ones. | |
| req-demo-govcloud-population-3 | Idempotent | Proposed | Re-running the population produces the same grid, with no duplicate nodes or edges. | |

### Deferred To The Zoom View
----
RID: `req-demo-govcloud-deferred`

Status: `Proposed`

Not part of the top view; recorded so they are not lost.

- **High availability:** two or more web tasks in two availability zones, autoscaling, the database standby. Ruled to a lower zoom level on 2026-10-13. Tracked in unified-systems-com/tap#1020.
- **Egress and VPC endpoints:** the private paths to ECR, Secrets Manager and logging, so containers need no route to the public internet. A zoom-level cluster inside the VPC.
- **Agents:** how agents take part in day-to-day operations. They are expected to come in through the same doors as the developer (GitHub) and the administrator (remote-access) and to leave the same audit trail; the layout reserves a slot beside each.
- **Cross-region backup copies** (GovCloud East and West), and the standby database drawn explicitly.
- **Subnets, security groups, IAM roles** as zoomable detail of the VPC.

## Status Vocabulary

Use these values consistently in the Requirements table and each requirement's `Status` line:

| Status States |  |
| --- | --- |
| Proposed | Hey everyone, here's an idea. |
| Approved for Development | Requirement is accepted and ready to be implemented. |
| In Development | Actively being worked on, see the Development section for more details. |
| Implemented | Has been written, see the Implementation section for how. |
| Verified | Has met the acceptance criteria as defined in that section. |
| Refactoring | In the process of being re-worked. |
| Deprecating | In the process of being deprecated. |
| Deprecated | Not part of the current architecture and should not be implemented. |

## Sources

- [Amazon Route 53 adds public authoritative DNS to AWS GovCloud (US) Regions, AWS announcement, April 2025](https://aws.amazon.com/about-aws/whats-new/2025/04/amazon-route-53-public-authoritative-dns-aws-govcloud-us-regions/)
