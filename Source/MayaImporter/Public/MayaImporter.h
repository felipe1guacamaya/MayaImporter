// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

// Forward declarations for toolbar extender
class FExtender;
class FToolBarBuilder;

class FMayaImporterModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

private:
    /** Called by ToolMenus at editor startup to add our toolbar button */
    void RegisterMenus();

    /** Executed when the toolbar button is clicked */
    void RunPythonScript();

    /** Classic extender callback */
    void AddToolbarButton(FToolBarBuilder& Builder);

    /** Keep reference so it doesn't get GC'd */
    TSharedPtr<FExtender> ToolbarExtender;

    /** Handle to unregister our ToolMenus startup callback on shutdown */
    FDelegateHandle ToolMenusStartupHandle;
};
