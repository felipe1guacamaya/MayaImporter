// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class MayaImporter : ModuleRules
{
    public MayaImporter(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "Slate",
            "SlateCore"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "UnrealEd",          // editor-only stuff
            "LevelEditor",       // to extend Level Editor UI
            "ToolMenus",         // modern menu/toolbar API
            "Projects",          // to locate plugin folder
            "PythonScriptPlugin" // to run Python from C++
        });
    }
}
