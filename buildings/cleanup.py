# TODO: All "AIRTERMINAL:SINGLEDUCT:UNCONTROLLED" change to "AirTerminal:SingleDuct:ConstantVolume:NoReheat"
# TODO: "AirTerminal:SingleDuct:ConstantVolume:NoReheat" add a comma before supply air line
# TODO: Add as "Zone Inlet <from next line> ATInlet,     !- Air Inlet Node Name"
# TODO: All "WindowProperty:ShadingControl" change to "WindowShadingControl"
# TODO: All Window should not have Shading Control Name
# TODO: All Window should have a new WindowSadingControl
# TODO: All "Boiler:HotWater" remove "Design Water Outlet Temperature {C}"
# TODO: "Sequential" in "PlantLoop" change to "SequentialLoad"
# TODO: "RunPeriod" add "End Year" and "Begin Year"
# TODO: "RunPeriod" remove "Day of Week for Start Day"
# TODO: "RunPeriod" last line change to "Yes" indicates "Treat Weather as Actual"
# TODO: Update version
# TODO: Add "SequentialLoad" after "ZoneHVAC:EquipmentList" Name field

'''

  Window,
      Window_ldf_unit2_FrontRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldf_1.unit2_FrontRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdr_unit3_FrontRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdr_1.unit3_FrontRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdl_unit3_FrontRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdl_1.unit1_FrontRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldf_unit3_FrontRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldf_1.unit3_FrontRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit1_BackRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit1_BackRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit2_BackRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit2_BackRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdr_unit3_BackRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdr_1.unit3_BackRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdl_unit3_BackRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdl_1.unit1_BackRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit3_BackRow_BottomFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit3_BackRow_BottomFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldf_unit1_FrontRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldf_1.unit1_FrontRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldf_unit2_FrontRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldf_1.unit2_FrontRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdr_unit3_FrontRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdr_1.unit3_FrontRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdl_unit3_FrontRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdl_1.unit1_FrontRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldf_unit3_FrontRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldf_1.unit3_FrontRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit1_BackRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit1_BackRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit2_BackRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit2_BackRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdr_unit3_BackRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdr_1.unit3_BackRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdl_unit3_BackRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdl_1.unit1_BackRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit3_BackRow_MiddleFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit3_BackRow_MiddleFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldf_unit1_FrontRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldf_1.unit1_FrontRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldf_unit2_FrontRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldf_1.unit2_FrontRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdr_unit3_FrontRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdr_1.unit3_FrontRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdl_unit3_FrontRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdl_1.unit1_FrontRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldf_unit3_FrontRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldf_1.unit3_FrontRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit1_BackRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit1_BackRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit2_BackRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit2_BackRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdr_unit3_BackRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdr_1.unit3_BackRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_sdl_unit3_BackRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_sdl_1.unit1_BackRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1,                       !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      6.75,                  !- Length {m}
      1.2195122;        !- Height {m}

  Window,
      Window_ldb_unit3_BackRow_TopFloor,  !- Name
      Exterior Window,         !- Construction Name
      Wall_ldb_1.unit3_BackRow_TopFloor,  !- Building Surface Name

      ,                        !- Frame and Divider Name
      1,                       !- Multiplier
      1.45724907063197,        !- Starting X Coordinate {m}
      0.914634146341463,       !- Starting Z Coordinate {m}
      4.5,                  !- Length {m}
      1.2195122;        !- Height {m}

'''