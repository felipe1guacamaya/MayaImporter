// Copyright Epic Games, Inc. All Rights Reserved.

#include "MayaImporter.h"
#include "ToolMenus.h"
#include "LevelEditor.h"
#include "Interfaces/IPluginManager.h"
#include "IPythonScriptPlugin.h"
#include "Misc/Paths.h"
#include "Misc/MessageDialog.h"
#include "Framework/MultiBox/MultiBoxBuilder.h" // for FToolBarBuilder

#define LOCTEXT_NAMESPACE "FMayaImporterModule"

void FMayaImporterModule::StartupModule()
{
    // Make sure LevelEditor is loaded
    FModuleManager::LoadModuleChecked<FLevelEditorModule>("LevelEditor");

    // Classic toolbar extender (shows after Settings group)
    ToolbarExtender = MakeShareable(new FExtender);
    ToolbarExtender->AddToolBarExtension(
        "Settings",
        EExtensionHook::After,
        nullptr,
        FToolBarExtensionDelegate::CreateRaw(this, &FMayaImporterModule::AddToolbarButton));

    FLevelEditorModule& LevelEditorModule = FModuleManager::LoadModuleChecked<FLevelEditorModule>("LevelEditor");
    LevelEditorModule.GetToolBarExtensibilityManager()->AddExtender(ToolbarExtender);

    // Keep ToolMenus registration too (optional, but harmless)
    ToolMenusStartupHandle = UToolMenus::RegisterStartupCallback(
        FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FMayaImporterModule::RegisterMenus));
}

void FMayaImporterModule::ShutdownModule()
{
    UToolMenus::UnRegisterStartupCallback(this);
    ToolbarExtender.Reset();
}

void FMayaImporterModule::RegisterMenus()
{
    UE_LOG(LogTemp, Warning, TEXT("MayaImporter: RegisterMenus called, wiring toolbar + Tools menu."));

    FToolMenuOwnerScoped OwnerScoped(this);

    // 1) Level Editor toolbar (keep this; it should appear after “Settings” or in the toolbar overflow)
    if (UToolMenu* ToolbarMenu = UToolMenus::Get()->ExtendMenu("LevelEditor.LevelEditorToolBar"))
    {
        FToolMenuSection& Section = ToolbarMenu->AddSection(
            "MayaImporterSection",
            LOCTEXT("MayaImporterSection", "Maya Importer"));

        Section.AddEntry(FToolMenuEntry::InitToolBarButton(
            "MayaImporterButton",
            FUIAction(FExecuteAction::CreateRaw(this, &FMayaImporterModule::RunPythonScript)),
            LOCTEXT("MayaImporterLabel", "Import from Maya"),
            LOCTEXT("MayaImporterTooltip", "Run Maya import Python script"),
            FSlateIcon(FAppStyle::GetAppStyleSetName(), "Icons.Import") // visible icon helps avoid collapse glitches
        ));
    }

    // 2) Main menu → Tools (always visible path: Tools → Maya Importer → Import from Maya)
    if (UToolMenu* ToolsMenu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Tools"))
    {
        FToolMenuSection& ToolsSection = ToolsMenu->AddSection(
            "MayaImporterToolsSection",
            LOCTEXT("MayaImporterToolsSection", "Maya Importer"));

        ToolsSection.AddMenuEntry(
            "MayaImporterMenuItem",
            LOCTEXT("MayaImporterMenuLabel", "Import from Maya"),
            LOCTEXT("MayaImporterMenuTooltip", "Run Maya import Python script"),
            FSlateIcon(FAppStyle::GetAppStyleSetName(), "Icons.Import"),
            FUIAction(FExecuteAction::CreateRaw(this, &FMayaImporterModule::RunPythonScript))
        );
    }

    UToolMenus::Get()->RefreshAllWidgets();
}

void FMayaImporterModule::AddToolbarButton(FToolBarBuilder& Builder)
{
    Builder.AddToolBarButton(
        FUIAction(FExecuteAction::CreateRaw(this, &FMayaImporterModule::RunPythonScript)),
        NAME_None,
        LOCTEXT("MayaImporterLabel_Classic", "Import from Maya"),
        LOCTEXT("MayaImporterTooltip_Classic", "Run Maya import Python script"),
        FSlateIcon()
    );
}

void FMayaImporterModule::RunPythonScript()
{
    IPythonScriptPlugin* Py = FModuleManager::LoadModulePtr<IPythonScriptPlugin>("PythonScriptPlugin");
    if (!Py)
    {
        FMessageDialog::Open(EAppMsgType::Ok, LOCTEXT("PythonNotAvailable", "Python Script Plugin is not available or enabled."));
        return;
    }

    TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin("MayaImporter");
    if (!Plugin.IsValid())
    {
        FMessageDialog::Open(EAppMsgType::Ok, LOCTEXT("PluginNotFound", "MayaImporter plugin not found."));
        return;
    }

    const FString PythonScriptPath = FPaths::Combine(Plugin->GetBaseDir(), TEXT("Content/Python/import_from_maya.py"));
    if (!FPaths::FileExists(PythonScriptPath))
    {
        FMessageDialog::Open(EAppMsgType::Ok, LOCTEXT("ScriptNotFound", "Python script not found at Content/Python/import_from_maya.py."));
        return;
    }

    Py->ExecPythonCommand(*FString::Printf(TEXT("exec(open(r\"%s\", 'r', encoding='utf-8').read())"), *PythonScriptPath));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FMayaImporterModule, MayaImporter)