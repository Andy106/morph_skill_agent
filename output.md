# Enumeration review: database-instance.schema-1.json

- **Schema:** `C:\D Drive\Software Engineering\AI Coder\morph_skill_agent\schemas\database-instance.schema-1.json`
- **Generated:** 2026-10-27 19:24
- **Enumeration Manager:** http://127.0.0.1:8000

Reviewed 7 enum/const attributes in database-instance.schema-1.json against the Enumeration Manager's 2 enumerations: 1 same, 0 similar, 6 different.

| Result | Attributes | Action |
| --- | --- | --- |
| Same | 1 | None needed |
| Similar | 0 | Change the JSON Schema to match the enumeration |
| Different | 6 | Add a new enumeration to the app |

## Same: no change needed

| Attribute | Pointer | Enumeration | Notes |
| --- | --- | --- | --- |
| `environment` | `/properties/environment` | `environment` | Values dev/test/prod exactly match the 'environment' enumeration, and the attribute already carries x-enumeration 'environment'. |

## Similar: proposed JSON Schema changes

None.

## Different: proposed new enumerations

### `engine`

- **Pointer:** `/properties/engine`
- **Schema values:** `oracle`, `postgresql`, `mysql`, `sqlserver`, `db2`

No app enumeration represents database engine; 'environment' and 'asset_types' are unrelated concepts.

Proposed enumeration `database_engine`. To create it:

```http
POST http://127.0.0.1:8000/api/enumerations
Content-Type: application/json

{
  "name": "database_engine",
  "description": "Database engine of a database instance.",
  "values": [
    "oracle",
    "postgresql",
    "mysql",
    "sqlserver",
    "db2"
  ]
}
```

### `edition`

- **Pointer:** `/properties/edition`
- **Schema values:** `Enterprise Edition`, `Standard Edition 2`, `Express Edition`, `Personal Edition`

No app enumeration represents engine edition.

Proposed enumeration `edition`. To create it:

```http
POST http://127.0.0.1:8000/api/enumerations
Content-Type: application/json

{
  "name": "edition",
  "description": "Engine edition of a database instance.",
  "values": [
    "Enterprise Edition",
    "Standard Edition 2",
    "Express Edition",
    "Personal Edition"
  ]
}
```

### `national_character_set`

- **Pointer:** `/properties/national_character_set`
- **Schema values:** `AL16UTF16`, `UTF8`

No app enumeration represents national character set.

Proposed enumeration `national_character_set`. To create it:

```http
POST http://127.0.0.1:8000/api/enumerations
Content-Type: application/json

{
  "name": "national_character_set",
  "description": "National character set of a database instance.",
  "values": [
    "AL16UTF16",
    "UTF8"
  ]
}
```

### `type`

- **Pointer:** `/properties/storage/properties/type`
- **Schema values:** `ASM`, `filesystem`, `cloud_block_storage`

No app enumeration represents storage type; name prefixed with parent for clarity.

Proposed enumeration `storage_type`. To create it:

```http
POST http://127.0.0.1:8000/api/enumerations
Content-Type: application/json

{
  "name": "storage_type",
  "description": "Storage type used by a database instance.",
  "values": [
    "ASM",
    "filesystem",
    "cloud_block_storage"
  ]
}
```

### `data_guard_role`

- **Pointer:** `/properties/high_availability/properties/data_guard_role`
- **Schema values:** `none`, `primary`, `physical_standby`, `logical_standby`

No app enumeration represents Data Guard role.

Proposed enumeration `data_guard_role`. To create it:

```http
POST http://127.0.0.1:8000/api/enumerations
Content-Type: application/json

{
  "name": "data_guard_role",
  "description": "Data Guard role of a database instance in a high availability configuration.",
  "values": [
    "none",
    "primary",
    "physical_standby",
    "logical_standby"
  ]
}
```

### `status`

- **Pointer:** `/properties/status`
- **Schema values:** `provisioning`, `running`, `stopped`, `maintenance`, `decommissioned`

No app enumeration represents operational status.

Proposed enumeration `database_instance_status`. To create it:

```http
POST http://127.0.0.1:8000/api/enumerations
Content-Type: application/json

{
  "name": "database_instance_status",
  "description": "Operational status of a database instance.",
  "values": [
    "provisioning",
    "running",
    "stopped",
    "maintenance",
    "decommissioned"
  ]
}
```
